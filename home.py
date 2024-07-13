import mesop as me
from repo_utils import is_valid_repolink, get_reponame, clone_github_repo, create_file_content_dict, delete_directory
from search_utils import filter_important_words, search_and_format, make_files_prompt, parse_arr_from_gemini_resp, content_str_from_dict
import pickle
import os
import mesop.labs as mel
from dotenv import load_dotenv
import google.generativeai as genai
from dataclasses import dataclass, field


load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

data_dir = '/home/rka/code/repo'
html_title = """
             <h1>Chat with GitHub repo using Gemini API(<a href="https://github.com/rakaar/chat_with_repo_gemini_api">code</a>)</h1>
              """
input_style_dict = {
          'font_size': 30,
          'width': '100%',
          'text_align': 'center',
      }

def on_input(e: me.InputBlurEvent):
  state = me.state(State)
  state.input = e.value

@me.stateclass
class RepoState:
   path2content_map: dict = field(default_factory=lambda: {}) 
   name: str = ''

@me.stateclass
class State:
  input: str = ""

@me.page(path="/")
def app():
  repo_state = me.state(RepoState)
  s = me.state(State)
  me.html(html_title)
  me.input(
      label="Github Repo link",
      on_input=on_input,
      style= input_style_dict
  )
  if is_valid_repolink(s.input):
    repolink = s.input
    reponame = get_reponame(repolink)
    repo_state.name = reponame.replace('+', '/')
    pkl_filename = f"{reponame}.pkl"
    

    if not os.path.exists(os.path.join(data_dir, pkl_filename)):
      repo_clone_path = f"{data_dir}/{reponame}"
      clone_github_repo(repolink, repo_clone_path)
      repo_dict = create_file_content_dict(repo_clone_path)
      repo_state.path2content_map = repo_dict
      with open(f'{data_dir}/{pkl_filename}', 'wb') as f:
          pickle.dump(repo_dict, f)
      delete_directory(repo_clone_path)
    else:
      with open(f"{data_dir}/{pkl_filename}", 'rb') as f:
         repo_state.path2content_map = pickle.load(f)

    # go to chat
    try:
       me.button(f"Chat with {repo_state.name}", on_click=nav_func, type="raised")
    except Exception as e:
       print('Erorr in navigating : ', e)


def nav_func(event: me.ClickEvent):
   me.navigate('/chat')

@me.page(path="/chat")
def page():
  repo_state = me.state(RepoState)
  mel.chat(transform, title=f"Using Gemini API - Chat with GitHub repo {repo_state.name}", bot_user="gemini_mesop_bot")
  

def transform_history_to_genai_history(transform_history):
    genai_history = []
    for message in transform_history:
        role = 'user' if message.role == 'user' else 'model'
        genai_history.append({
            'role': role,
            'parts': [{'text': message.content}]
        })
    return genai_history

def transform(input: str, history: list[mel.ChatMessage]):
   repo_state = me.state(RepoState)
   repo_dict = repo_state.path2content_map
   
   important_words = filter_important_words(input)
   try:
       relevant_code = search_and_format(repo_dict, important_words)
       token_count =  model.count_tokens(relevant_code)
       if token_count > 1e6:
           raise Exception('Token count exceeded')
   except Exception as e:
       print('Ask Gemini what files might be used')
       files_prompt = make_files_prompt(repo_dict, input)
       response = model.generate_content(files_prompt)
       required_files = parse_arr_from_gemini_resp(response.text)
       print(f'Num of suggested files = {len(required_files)}')
       relevant_code = content_str_from_dict(repo_dict, required_files)

   input_to_LLM = "'''\n" + relevant_code + "\n'''\n" + "Use the above code if necessary." + input
  #  print('input_to_LLM=', input_to_LLM)
   genai_history = transform_history_to_genai_history(history)	
   chat = model.start_chat(history=genai_history)
   try:
       response = chat.send_message(input_to_LLM, stream=True)
       for chunk in response:
           yield chunk.text
   except Exception as e:
       yield "An error occured. Gemini seems to categroy your query as unsafe."
       print('error in response = chat.send mess: ',e)

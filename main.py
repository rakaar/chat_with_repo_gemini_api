import mesop as me
from repo_utils import is_valid_repolink, get_reponame, clone_github_repo, create_file_content_dict, delete_directory
from search_utils import make_files_prompt, parse_arr_from_gemini_resp, content_str_from_dict, make_all_files_content_str
import os
import mesop.labs as mel
from dotenv import load_dotenv
import google.generativeai as genai
from dataclasses import field


load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

data_dir = './repo'
html_title = """
             <h1>Chat with GitHub repo using Gemini API(<a href="https://github.com/rakaar/chat_with_repo_gemini_api">code</a>)</h1>
              """
input_style_dict = {
          'font_size': 30,
          'width': '100%',
          'text_align': 'center',
      }

def nav_func(event: me.ClickEvent):
   print('navigating to chat')
   me.navigate('/chat')

def on_input(e: me.InputBlurEvent):
  state = me.state(InputState)
  state.input = e.value

@me.stateclass
class RepoState:
   path2content_map: dict = field(default_factory=lambda: {}) 
   name: str = ''
   entire_code: str = ''
   is_entire_code_loaded: int = -1
   is_repo_cloned: bool = False  

@me.stateclass
class InputState:
  input: str = ""

@me.page(path="/")
def app():
  repo_state = me.state(RepoState)
  s = me.state(InputState)
  me.html(html_title)
  me.input(
      label="Github Repo link",
      on_input=on_input,
      style= input_style_dict
  )

  if is_valid_repolink(s.input) and not repo_state.is_repo_cloned:
    repolink = s.input
    reponame = get_reponame(repolink)
    repo_state.name = reponame.replace('+', '/')
    repo_clone_path = f"{data_dir}/{reponame}"
    clone_github_repo(repolink, repo_clone_path)
    repo_dict = create_file_content_dict(repo_clone_path)
    delete_directory(repo_clone_path)
    
    # go to chat
    repo_state.path2content_map = repo_dict
    repo_state.entire_code = make_all_files_content_str(repo_dict)

    repo_state.is_repo_cloned = True
    try:
       print('Showing button')
       me.button(f"Chat with {repo_state.name}", on_click=lambda event: me.navigate('/chat'), type="raised")
    except Exception as e:
       print('Erorr in navigating : ', e)




@me.page(path="/chat")
def page1():
   me.text('This page issue?')

@me.page(path="/cat")
def page():
  repo_state = me.state(RepoState)
  mel.chat(transform, title=me.html(f"<h2>Chat with {repo_state.name} | <a href='/'> Change Repo </a> </h2>"), bot_user="gemini_mesop_bot")
  

def transform_history_to_genai_history(transform_history, is_entire_code_loaded, entire_code, prompt_to_use_codebase):
    genai_history = []
    for message in transform_history:
        role = 'user' if message.role == 'user' else 'model'
        genai_history.append({
            'role': role,
            'parts': [{'text': message.content}]
        })
    
    if is_entire_code_loaded == 1:
       first_user_query = genai_history[0]['parts'][0]['text']
       first_user_query_modfied = f"'''\n{entire_code}\n'''\n {prompt_to_use_codebase}.{first_user_query}?"
       genai_history[0]['parts'][0]['text'] = first_user_query_modfied

    return genai_history

def transform(input: str, history: list[mel.ChatMessage]):
   repo_state = me.state(RepoState)
   repo_dict = repo_state.path2content_map
   entire_code = repo_state.entire_code

   if repo_state.is_entire_code_loaded == -1:
       try:
          num_tokens_code = model.count_tokens(entire_code).total_tokens
          print(f'Num of tokens in code = {num_tokens_code}')
       except:
          num_tokens_code = 1e6
      
       if num_tokens_code > 1e6-10e3:
          repo_state.is_entire_code_loaded = 0
       else:
          repo_state.is_entire_code_loaded = 1
   
   prompt_to_use_codebase = "Use the above code if necessary. Preferably answer the below question by citing the filepath and the code"
   if repo_state.is_entire_code_loaded == 0:
      print('Ask Gemini what files might be used')
      files_prompt = make_files_prompt(repo_dict, input)
      response = model.generate_content(files_prompt)
      required_files = parse_arr_from_gemini_resp(response.text)
      print(f'Num of suggested files = {len(required_files)}')
      relevant_code = content_str_from_dict(repo_dict, required_files)
   elif repo_state.is_entire_code_loaded == 1:
      if len(history) == 2:
         print('Loading entire codebase')
         relevant_code = entire_code
      else:
         relevant_code = ''; prompt_to_use_codebase = ''
          
   input_to_LLM = f"'''\n{relevant_code}\n'''\n {prompt_to_use_codebase}.{input}?"  
   genai_history = transform_history_to_genai_history(history, repo_state.is_entire_code_loaded, entire_code, prompt_to_use_codebase)	
   chat = model.start_chat(history=genai_history)
   try:
       response = chat.send_message(input_to_LLM, stream=True)
       for chunk in response:
           yield chunk.text
   except Exception as e:
       yield "An error occured. Gemini seems to categroy your query as unsafe."
       print('error in response = chat.send mess: ',e)
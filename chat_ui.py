import random
import time

import mesop as me
import mesop.labs as mel

from repo_utils import *
import pickle

repo_dict = {}

import google.generativeai as genai
GOOGLE_API_KEY=''
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


repo_url = "https://github.com/rakaar/repo2text"  # Replace with your repository URL
clone_path = ""
if clone_path == "":
      clone_path = f"./repo/{get_clone_path_dir(repo_url)}"
      if not os.path.exists(clone_path):
         print(f"Cloing {repo_url} at {clone_path}")
         clone_github_repo(repo_url, clone_path)
         print(f"Repository cloned to {clone_path}")


if not repo_dict:
          pkl_filename = f"{get_clone_path_dir(repo_url)}.pkl"
          if os.path.exists(os.path.join(clone_path, pkl_filename)):
              with open(os.path.join(clone_path, pkl_filename), 'rb') as f:
                  repo_dict = pickle.load(f)
          else:
            repo_dict = create_file_content_dict(clone_path)
            with open(os.path.join(clone_path, pkl_filename), 'wb') as f:
                pickle.dump(repo_dict, f)
            print('repo_dict created')
        
@me.page(
   path="/chat",
  title="Mesop Demo Chat",
)
def page():
  mel.chat(transform, title="Github Repo Chat with Gemini API", bot_user="gemini_mesop_bot")


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
   global repo_dict
   global clone_path
  
   print('repo_dict After ', repo_dict)
   important_words = filter_important_words(input)
   try:
       relevant_code = search_and_format(repo_dict, important_words)
       token_count =  model.count_tokens(relevant_code)
       if token_count > 1e6:
           raise Exception('Token count exceeded')
   except Exception as e:
       print('Ask Gemini what files might be used')
       files_promot = make_files_prompt(repo_dict, input)
       response = model.generate_content(files_promot)
       required_files = parse_arr_from_gemini_resp(response.text)
       print(f'Suggested files are {required_files}')
       relevant_code = content_str_from_dict(repo_dict, required_files)

   print(relevant_code)       
   input_to_LLM = "'''\n" + relevant_code + "\n'''\n" + "Use the above code if necessary." + input
   
   genai_history = transform_history_to_genai_history(history)	
   chat = model.start_chat(history=genai_history)
   try:
       response = chat.send_message(input_to_LLM, stream=True)
       for chunk in response:
           yield chunk.text
   except Exception as e:
       yield "An error occured sorry"
       print(e)

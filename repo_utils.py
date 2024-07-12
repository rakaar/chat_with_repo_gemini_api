import git
import os
import re
import concurrent.futures
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string
import chardet
import chardet
import json
import shutil


nltk.download('stopwords')
nltk.download('punkt')


def delete_directory(repo_clone_path):
    try:
        shutil.rmtree(repo_clone_path)
        print(f"Successfully deleted directory: {repo_clone_path}")
    except Exception as e:
        print(f"Error deleting directory {repo_clone_path}: {e}")


def get_reponame(repo_url):
    repo_url = repo_url.rstrip('/')
    
    parts = repo_url.split('/')
    username = parts[3]
    reponame = parts[4]

    # Check if the URL contains a branch
    if len(parts) > 5 and parts[5] == 'tree':
        branchname = parts[6]
        combined_string = f"{username}+{reponame}+{branchname}"
    else:
        combined_string = f"{username}+{reponame}"

    return combined_string



def clone_github_repo(repo_url, clone_path):
    try:
        repo_url = repo_url.rstrip('/')

        pattern = re.compile(r'^https://github\.com/([^/]+)/([^/]+)(/tree/([^/]+))?$')
        match = pattern.match(repo_url)

        if not match:
            raise ValueError("Invalid GitHub repository URL")

        username, reponame, _, branchname = match.groups()

        base_repo_url = f"https://github.com/{username}/{reponame}.git"
        if not os.path.exists(clone_path):
            os.makedirs(clone_path)

        if branchname:
            git.Repo.clone_from(base_repo_url, clone_path, branch=branchname)
        else:
            git.Repo.clone_from(base_repo_url, clone_path)
        
        print(f"Repository cloned to {clone_path}")
    except Exception as e:
        print(f"Failed to clone repository: {e}")


def is_valid_repolink(repolink):
    pattern = re.compile(r'^https://github\.com/[^/]+/[^/]+(/tree/[^/]+)?$')
    return bool(pattern.match(repolink))

def process_file(file_path, clone_path):
    relative_path = os.path.relpath(file_path, clone_path)
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            if file_path.endswith('.ipynb'):
                # Handle Jupyter notebook files
                try:
                    content = json.loads(raw_data)
                    cell_sources = [
                        ''.join(cell.get('source', ''))
                        for cell in content.get('cells', [])
                        if cell.get('cell_type') in ('markdown', 'code')
                    ]
                    text = '\n'.join(cell_sources)
                    return relative_path, text
                except json.JSONDecodeError as e:
                    print(f"Failed to parse notebook {file_path}: {e}")
                    return None
            else:
                # Handle other text files
                result = chardet.detect(raw_data)
                encoding = result['encoding']
                if encoding is not None:
                    text = raw_data.decode(encoding)
                    return relative_path, text
                else:
                    print(f"Skipping non-text file: {file_path}")
                    return None
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return None

def create_file_content_dict(clone_path):
    file_content_dict = {}
    files_to_process = []

    for root, _, files in os.walk(clone_path):
        if '/.git/' in root:
            continue
        for file in files:
            file_path = os.path.join(root, file)
            files_to_process.append(file_path)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_file, file_path, clone_path): file_path for file_path in files_to_process}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                relative_path, text = result
                file_content_dict[relative_path] = text

    return file_content_dict



def search_and_format(file_content_dict, search_terms):
    results = []
    search_pattern = re.compile('|'.join(map(re.escape, search_terms)), re.IGNORECASE)

    def search_in_file(path, content):
        if search_pattern.search(path) or search_pattern.search(content):
            result = f"===\nFilename: {path}\n\nContent:\n```\n{content}\n```\n===\n"
            return result
        return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(search_in_file, path, content) for path, content in file_content_dict.items()]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return ''.join(results)



def filter_important_words(query):
    stop_words = set(stopwords.words('english'))
    word_tokens = word_tokenize(query)
    important_words = [word for word in word_tokens if word.lower() not in stop_words and word not in string.punctuation]
    return important_words


def make_files_prompt(repo_dict, user_query):
    key_string = "\n".join(repo_dict.keys())
    print('key string ', key_string, 'dict keys ', repo_dict.keys())
    files_prompt = f"""{key_string}.
Above is the file structure of github codebase. 
To answer {user_query}, what files might be required. 
Reply the filenames as a python array. Your response format should be ['filename1.type, filename2.type']"""
    
    return files_prompt

def parse_arr_from_gemini_resp(text):
    pattern = re.compile(r'\[\s*([\s\S]*?)\s*\]', re.MULTILINE)
    match = pattern.search(text)
    if match:
        array_content = match.group(1)
        array_elements = [element.strip().strip("'\"") for element in array_content.split(',') if element.strip()]
        return array_elements
    else:
        return ['README.md', 'readme.md']
    


def content_str_from_dict(repo_dict, pathnames):
    result = ''
    for path in pathnames:
        content = repo_dict.get(path)
        result += f"===\nFilename: {path}\n\nContent:\n```\n{content}\n```\n===\n"
    return result

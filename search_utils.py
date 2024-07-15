import re
import concurrent.futures
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string


nltk.download('stopwords')
nltk.download('punkt')


def make_all_files_content_str(repo_dict):
    formatted_string = ""
    for filepath, content in repo_dict.items():
        formatted_string += f"===\nFilepath: {filepath}\n\n File content:\n{content}\n\n"
    return formatted_string

def filter_important_words(query):
    stop_words = set(stopwords.words('english'))
    word_tokens = word_tokenize(query)
    important_words = [word for word in word_tokens if word.lower() not in stop_words and word not in string.punctuation]
    return important_words


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


def make_files_prompt(repo_dict, user_query):
    key_string = "\n".join(repo_dict.keys())
    # print('key string ', key_string, 'dict keys ', repo_dict.keys())
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


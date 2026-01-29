from openai import OpenAI
from google import genai
from anthropic import Anthropic
import requests
import argparse
import os

# function to check models from Google available through API 
def check_google_api_models():
    api_key = None
    if os.environ.get("GOOGLE_API_KEY"):
        api_key = os.environ.get("GOOGLE_API_KEY")
    else:
        raise Exception("GOOGLE_API_KEY key is not available or set as an environment variable")

    client = genai.Client(api_key=api_key)
    print("List of models that support generateContent:\n")
    for model in client.models.list():
        for action in model.supported_actions:
            if action == "generateContent":
                print(model.name)

# function to check models from OpenAI available through API
def check_opeai_api_models():    
    api_key = None
    if os.environ.get("OPENAI_API_KEY"):
        api_key = os.environ.get("OPENAI_API_KEY")
    else:
        raise Exception("OpenAI_API_KEY key is not available or set as an environment variable")
    
    client = OpenAI(api_key=api_key)
    # list OpenAI API models 
    models = client.models.list()
    for model in models:
        print(model.id)
        
# function to check models from MetaAI available through API        
def check_llama_api_models():
    api_key = None 
    if os.environ.get("GROQ_API_KEY"):
        api_key = os.environ.get("GROQ_API_KEY")
    else:
        raise Exception("GROQ_API_KEY key is not available or set as an environment variable")
    
    url = "https://api.groq.com/openai/v1/models"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    print(response.json())

# function to check models from Anthropic available through API
def check_anthropic_api_models():
    client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"), 
    )
    
    page = client.models.list()
    for model in page.data:
        print(model.id)

    page = page.data[0]
    print(page.id)    

# function to parse command line argument and 
# display available API models for the provided provider
def check_models_available_through_api():
    cmd_parser = argparse.ArgumentParser(prog="API model checker", description="Comand line parser for checking available API models from OpenAI, Google, Anthropic, and MetaAI")
    cmd_parser.add_argument("--api-provider", type=str, default=None, choices=["openai", "google", "anthropic", "llama"] ,help="provide one of the following options as a model provider: openai | google | anthropic | llama")
    
    cmd_args = cmd_parser.parse_args()
    if not cmd_args.api_provider:
        raise Exception("You didn't provide a valid provider please use check_available_model.py --help to see usage details")
    
    model_provider = cmd_args.api_provider
    if model_provider == "openai":
        check_opeai_api_models()
    elif model_provider == "google":
        check_google_api_models()
    elif model_provider == "anthropic":
        check_anthropic_api_models()
    else:
        check_llama_api_models()
       
# run API model checker    
if __name__ == "__main__": 
  check_models_available_through_api()    

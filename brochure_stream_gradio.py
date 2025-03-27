# imports
import os
import requests
import json
from typing import List
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI

import gradio as gr


# Initialize and constants
load_dotenv(override=True)
api_key = os.getenv('OPENAI_API_KEY')

if api_key and api_key.startswith('sk-proj-') and len(api_key)>10:
    print("API key looks good so far")
else:
    print("There might be a problem with your API key? Please visit the troubleshooting notebook!")
    
MODEL = 'gpt-4o-mini'
openai = OpenAI()


################################################### Parse website content feature ############################################################
# A class to represent a Webpage
# Some websites need you to use proper headers when fetching them:
headers = {
 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}

class Website:
    """
    A utility class to represent a Website that we have scraped, now with links
    """

    def __init__(self, url):
        self.url = url
        response = requests.get(url, headers=headers)
        self.body = response.content
        soup = BeautifulSoup(self.body, 'html.parser')
        self.title = soup.title.string if soup.title else "No title found"
        if soup.body:
            for irrelevant in soup.body(["script", "style", "img", "input"]):
                irrelevant.decompose()
            self.text = soup.body.get_text(separator="\n", strip=True)
        else:
            self.text = ""
        links = [link.get('href') for link in soup.find_all('a')]
        self.links = [link for link in links if link]

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"
    


############################################## Getting all relevant links and information feature #############################################
############################################## SYSTEM PROMPT ##################################################################################
# system prompt that uses specific structured output and one-shot prompting method
LINK_SYSTEM_PROMPT = "You are provided with a list of links found on a webpage. \
You are able to decide which of the links would be most relevant to include in a brochure about the company, \
such as links to an About page, or a Company page, or Careers/Jobs pages.\n"
LINK_SYSTEM_PROMPT += "You should respond in JSON as in this example:"
LINK_SYSTEM_PROMPT += """
{
    "links": [
        {"type": "about page", "url": "https://full.url/goes/here/about"},
        {"type": "careers page": "url": "https://another.full.url/careers"}
    ]
}
"""


############################################## functions definitions #############################################################################
# generate user_prompt to get appropriate links from the total list of links
def get_links_user_prompt(website):
    user_prompt = f"Here is the list of links on the website of {website.url} - "
    user_prompt += "please decide which of these are relevant web links for a brochure about the company, respond with the full https URL in JSON format. \
Do not include Terms of Service, Privacy, email links.\n"
    user_prompt += "Links (some might be relative links):\n"
    user_prompt += "\n".join(website.links)
    return user_prompt


# get links with the usage of system and user prompts via openai api
def get_links(url):
    website = Website(url)
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": LINK_SYSTEM_PROMPT},
            {"role": "user", "content": get_links_user_prompt(website)}
      ],
        response_format={"type": "json_object"}
    )
    result = response.choices[0].message.content
    return json.loads(result)


# Assemble all the details into another prompt to GPT4-o to create a brochure
def get_all_details(url):
    result = "Landing page:\n"
    result += Website(url).get_contents()
    links = get_links(url)
    print("Found links:", links)
    for link in links["links"]:
        result += f"\n\n{link['type']}\n"
        result += Website(link["url"]).get_contents()
    return result


############################################## Generate a brochure content feature ############################################################
############################################## SYSTEM PROMPT ##################################################################################
# system_prompt = "You are an assistant that analyzes the contents of several relevant pages from a company website \
# and creates a short brochure about the company for prospective customers, investors and recruits. Respond in markdown.\
# Include details of company culture, customers and careers/jobs if you have the information."

# Or uncomment the lines below for a more humorous brochure - this demonstrates how easy it is to incorporate 'tone':

SYSTEM_PROMPT = "You are an assistant that analyzes the contents of several relevant pages from a company website \
and creates a short humorous, entertaining, jokey brochure about the company for prospective customers, investors and recruits. Respond in markdown.\
Include details of company culture, customers and careers/jobs if you have the information."


############################################# function definitions ############################################################################
# compose a user prompt for the brochure creation
def get_brochure_user_prompt(company_name, url):
    user_prompt = f"You are looking at a company called: {company_name}\n"
    user_prompt += f"Here are the contents of its landing page and other relevant pages; use this information to build a short brochure of the company in markdown.\n"
    user_prompt += get_all_details(url)
    user_prompt = user_prompt[:5_000] # Truncate if more than 5,000 characters
    return user_prompt


# create a brochure via openai api based on prepared information
def create_brochure_stream(company_name, url):
    stream = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": get_brochure_user_prompt(company_name, url)}
          ],
        stream=True
    )
    
    response = ""
      
    for chunk in stream:
        response += chunk.choices[0].delta.content or ''
        yield response
    
    
################################################## MAIN PROGRAM RUN ###########################################################################
# create Gradio UI to get inputs from the user
view = gr.Interface(
    fn=create_brochure_stream,
    inputs=[gr.Textbox(label="name of the site:", lines=1), gr.Textbox(label="put url here:", lines=1)],
    outputs=[gr.Markdown(label="Response:")],
    flagging_mode="never"
)
view.launch()

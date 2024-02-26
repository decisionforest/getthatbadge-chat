# Import necessary libraries
import openai, os, requests
from openai import AzureOpenAI
from flask import Flask, render_template, request, jsonify
import re
from os import environ
from flask_swagger_ui import get_swaggerui_blueprint
from pdb import set_trace

# Create a Flask app
app = Flask(__name__)

# Swagger configuration
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
SWAGGER_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "app",  # Replace with your app name
        'validatorUrl': None  # Disable Swagger validator
    }
)
app.register_blueprint(SWAGGER_BLUEPRINT, url_prefix=SWAGGER_URL)

# Configure Azure OpenAI
openai.api_type = "azure"
openai.api_version = "2023-08-01-preview"
openai.api_base = environ['OPENAI_ENDPOINT']  # Add your endpoint here
openai.api_key = environ['OPENAI_KEY']  # Add your OpenAI API key here
deployment_id = environ['GPT35TURBO']  # Add your deployment ID here

# Configure Azure Cognitive Search
search_endpoint = "YOUR_SEARCH_ENDPOINT"  # Add your Azure Cognitive Search endpoint here
search_key = "YOUR_SEARCH_ADMIN_KEY"  # Add your Azure Cognitive Search admin key here
search_index_name = "YOUR_SEARCH_INDEX_NAME"  # Add your Azure Cognitive Search index name here

session = None

# Function to remove document references from the response
def remove_doc_references(response):
    return re.sub(r'\[doc\d+\]', '', response)

# Function to set up BYOD
def setup_byod(deployment_id: str) -> None:
    class BringYourOwnDataAdapter(requests.adapters.HTTPAdapter):
        def send(self, request, **kwargs):
            request.url = f"{openai.api_base}/openai/deployments/{deployment_id}/extensions/chat/completions?api-version={openai.api_version}"
            return super().send(request, **kwargs)

    session = requests.Session()
    session.mount(
        prefix=f"{openai.api_base}/openai/deployments/{deployment_id}",
        adapter=BringYourOwnDataAdapter()
    )
    openai.requestssession = session

client = AzureOpenAI(
        api_key = environ["OPENAI_KEY"],  
        api_version = "2023-09-01-preview",
        azure_endpoint = environ['OPENAI_ENDPOINT']
        )

# Define routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    setup_byod(deployment_id)
    user_question = request.form.get('question')

    completion = client.chat.completions.create(
        model=environ['GPT35TURBO'],
        messages=[
            {"role": "system", "content": 'You are a Cloud engineering educator and trainer.'},
            {"role": "user", "content": user_question}
            
        ],
        temperature=0,
        max_tokens=500,
    )

    ai_response = completion.choices[0].message.content
    ai_response = remove_doc_references(ai_response)
    return jsonify({'response': ai_response})

test = """
    def ask():
        setup_byod(deployment_id)
        user_question = request.form.get('question')
        conversation_history.append({"role": "user", "content": user_question})
        completion = openai.ChatCompletion.create(
            messages=conversation_history,
            deployment_id=deployment_id,
            maxResponseLength=800,
            temperature=0,
            topProbablities=1,
            pastMessagesToInclude=10,
            frequencyPenalty=0,
            presencePenalty=0,
            dataSources=[{
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": search_endpoint,
                    "key": search_key,
                    "indexName": search_index_name,
                }
            }]
        )
        ai_response = completion['choices'][0]['message']['content']
        ai_response = remove_doc_references(ai_response)
        conversation_history.append({"role": "assistant", "content": ai_response})
        return jsonify({'response': ai_response})
    """
@app.route('/api_get_response', methods=['GET'])
def get_response():
    ai_response = conversation_history[-1]['content']
    return jsonify({'response': ai_response})

if __name__ == '__main__':
    app.run()
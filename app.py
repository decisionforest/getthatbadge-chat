# Import necessary libraries
import openai, os, requests
from openai import AzureOpenAI
from flask import Flask, render_template, request, jsonify, abort
import re
from os import environ
from flask_swagger_ui import get_swaggerui_blueprint
from pdb import set_trace
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timedelta


# Create a Flask app
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = environ['CONNECTION_STRING_DIGITALOCEAN']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    last_activity_date = db.Column(db.DateTime, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    question = db.Column(db.String(300), nullable=False)
    search_index = db.Column(db.String(30), nullable=False)

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
azure_endpoint = environ['OPENAI_ENDPOINT']  # Add your endpoint here
api_key = environ['OPENAI_KEY']  # Add your OpenAI API key here
deployment_id = environ['GPT35TURBO']  # Add your deployment ID here

# Configure Azure Cognitive Search
search_endpoint = environ['SEARCH_ENDPOINT']  # Add your Azure Cognitive Search endpoint here
search_key = environ['SEARCH_KEY']  # Add your Azure Cognitive Search admin key here
#this is dynamic
#search_index_name = "databricks-docs-index"  # Add your Azure Cognitive Search index name here

session = None
conversation_history = []
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

#client = AzureOpenAI(api_key = environ["OPENAI_KEY"],  api_version = "2023-09-01-preview",azure_endpoint = environ['OPENAI_ENDPOINT'])

client = openai.AzureOpenAI(
        base_url=f"{azure_endpoint}/openai/deployments/{deployment_id}/extensions",
        api_key=api_key,
        api_version="2023-09-01-preview"
    )
 
# Define routes
@app.route('/')
def home():
    
    referer = request.headers.get('Referer')
    username = request.args.get('username')
    searchindex = request.args.get('searchindex')

    # If username is not in url, block access
    if not request.args.get('username'):
        abort(403)  # Forbidden access

    if referer and 'getthatbadge.com' in referer:
        return render_template('index.html', username=username, searchindex=searchindex)
    else:
        # Handle the case where it's not from the expected site
        #abort(403)  # Forbidden access COMMENT THIS OUT IN PROD, COMMENT IN DEV
        return render_template('index.html', username=username, searchindex=searchindex)
    

@app.route('/ask', methods=['POST'])
def ask():
    # Get username from the form or JSON data
    user = request.form.get('username')
    # Get username from the form or JSON data
    searchindex = request.form.get('searchindex')
    if searchindex == 'Databricks':
        search_index_name = "databricks-docs-index"  # Add your Azure Cognitive Search index name here
    else:
        search_index_name = ""  # Change here when a new index is added 

    # Query the UserActivity table for the current user
    user_activity = UserActivity.query.filter_by(username=user).first()

    if user == 'dan':
        ai_response = None
    else:
        # Calculate the date one year ago
        one_year_ago = datetime.utcnow() - timedelta(days=360)
        # Query the UserActivity table for the current user's activities in the last year
        recent_activities_count = UserActivity.query \
            .filter(UserActivity.username == user, UserActivity.last_activity_date >= one_year_ago) \
            .count()
        
        #modify this to change the number of requests allowed per month
        if recent_activities_count >= 25:
            # Handle the case where the user has more than 50 counts in the past month
            # For example, return an error message or abort the request
            ai_response = 'Limit exceeded. Contact us for a limit increase.'
        else:
            print(f'Total Count is {recent_activities_count}')
            ai_response = None   
    
    #if there's an ai response it means the limit has been exceeded
    if not ai_response:
        user_question = request.form.get('question')

        # Create a new record for new user
        user_activity = UserActivity(username=user, count=1, last_activity_date=datetime.utcnow(), question=user_question[:299], search_index=searchindex)
        db.session.add(user_activity)
        db.session.commit()
    
        completion = client.chat.completions.create(
            model=deployment_id,
            messages=[
                {"role": "user", "content": user_question}   
            ],
            temperature=0,
            max_tokens=500,
            extra_body={
                "dataSources": [
                    {
                        "type": "AzureCognitiveSearch",
                        "parameters": {
                            "endpoint": search_endpoint,
                            "indexName": search_index_name,
                            "semanticConfiguration": "default",
                            "queryType": "semantic",
                            "fieldsMapping": {},
                            "inScope": True,
                            "roleInformation": """
                            You are an AI Engineer here to help users pass the exam.
                            You never say that you retrieved documents, just say knowledge base.
                            If the user asks ambiguous questions, ask for more clarity.
                            You are always polite and helpful.
                            """,
                            "filter": None,
                            "strictness": 3,
                            "topNDocuments": 2,
                            "key": search_key
                            }
                    }
                ]
            },
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
    app.run(debug=False)
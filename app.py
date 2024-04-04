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

    # Query the UserActivity table, filter by username,
    # order by last_activity_date in descending order, and fetch the first result
    last_activity = UserActivity.query.filter_by(username=username) \
        .order_by(UserActivity.last_activity_date.desc()) \
        .first()

    if last_activity:
        nr_of_available_requests = last_activity.count
    else:
        # Handle the case where the user has no activities
        #Create a new record for new user directly with 25
        user_activity = UserActivity(username=username, count=25, last_activity_date=datetime.utcnow(), question='Entered Chat', search_index=searchindex)
        db.session.add(user_activity)
        db.session.commit()
        #setting the default
        nr_of_available_requests = 25

    # If username is not in url, block access
    if not request.args.get('username'):
        abort(403)  # Forbidden access

    if referer and 'getthatbadge.com' in referer:
        return render_template('index.html', username=username, searchindex=searchindex, nr_of_available_requests=nr_of_available_requests)
    else:
        # Handle the case where it's not from the expected site
        abort(403)  # Forbidden access DON'T COMMENT IN PROD, COMMENT IN DEV
        return render_template('index.html', username=username, searchindex=searchindex, nr_of_available_requests=nr_of_available_requests)
    

@app.route('/ask', methods=['POST'])
def ask():
    # Get username from the form or JSON data
    user = request.form.get('username')
    # Get username from the form or JSON data
    # Add your Azure Cognitive Search index name here
    searchindex = request.form.get('searchindex')
    if searchindex == 'Databricks':
        search_index_name = "databricks-docs-index"
    elif searchindex == 'AI900':
        search_index_name = "azure-ai-900-docs-index"
    elif searchindex == 'AI102':
        search_index_name = "azure-ai-102-docs-index"
    elif searchindex == 'AZ204':
        search_index_name = "azure-az-204-docs-index"
    else:
        search_index_name = ""

    # Find the most recent activity for the user
    user_activity = UserActivity.query.filter_by(username=user).order_by(UserActivity.last_activity_date.desc()).first()

    #if there are no available requests and the user is not the admin, the limit has been reached
    if user_activity and (user_activity.count == 0) and (user != 'dan'):
        ai_response = 'Limit exceeded. Contact us for a limit increase.'
    else:
        ai_response = None

    # if there's an ai response it means the limit has been exceeded
    # if there's no ai response we can go ahead to:
    # decrease the count
    # get a response
    if not ai_response:
        user_question = request.form.get('question')

        # Decrease the number of available requests
        decrease = user_activity.count - 1
        # add last activity
        last_activity = UserActivity(username=user, count=decrease, last_activity_date=datetime.utcnow(), question=user_question[:299], search_index=searchindex)
        db.session.add(last_activity)
        db.session.commit()
    
        completion = client.chat.completions.create(
            model=deployment_id,
            messages=[
                {"role": "system", "content": "You are a Microsoft Azure and Databricks educator and trainer that helps people learn by answering questions about Microsoft Azure and Databricks. You are helping people to prepare for cloud certification exams."},
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
    app.run(debug=False)
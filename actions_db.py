from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import inspect
from os import environ
from pdb import set_trace
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = environ['CONNECTION_STRING_DIGITALOCEAN']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), nullable=False)
    last_activity_date = db.Column(db.DateTime, default=datetime.utcnow)
    count = db.Column(db.Integer, default=0)
    question = db.Column(db.String(300), nullable=False)
    search_index = db.Column(db.String(30), nullable=False)

def create_tables():
    #only run this once at the beginning
    with app.app_context():
        db.create_all()

def ensure_table_exists():
    with app.app_context():
        # Create an inspector object
        inspector = inspect(db.engine)

        # Check if table exists
        if UserActivity.__tablename__ not in inspector.get_table_names():
            print(f"Table '{UserActivity.__tablename__}' does not exist.")
        else:
            print(f"Table '{UserActivity.__tablename__}' already exists.")

def drop_table(tablename):
    with app.app_context():
        meta = MetaData()
        meta.reflect(bind=db.engine)
        if tablename in meta.tables:
            try:
                table = Table(tablename, meta)
                table.drop(db.engine)
                print(f"Table '{tablename}' dropped successfully.")
            except SQLAlchemyError as e:
                print(f"Error occurred: {e}")
        else:
            print(f"Table '{tablename}' does not exist.")


def check_user_activities():
    with app.app_context():
        activities = UserActivity.query.all()
        
        for activity in activities:
            print(f"ID: {activity.id}, Username: {activity.username}, Last Activity: {activity.last_activity_date}, Count: {activity.count}, Question: {activity.question}, Search Index: {activity.search_index}")
if __name__ == '__main__':
    #create_tables()
    #ensure_table_exists()
    #drop_table('user_activity')
    check_user_activities()
    app.run(debug=True)  # Add this line to run your Flask app

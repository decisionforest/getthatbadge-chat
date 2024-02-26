from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import inspect
from pdb import set_trace

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mydatabase.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), unique=True, nullable=False)
    last_activity_date = db.Column(db.DateTime, default=datetime.utcnow)
    count = db.Column(db.Integer, default=0)

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
            print(f"Table '{UserActivity.__tablename__}' does not exist. Creating now.")
        else:
            print(f"Table '{UserActivity.__tablename__}' already exists.")

def check_user_activities():
    with app.app_context():
        activities = UserActivity.query.all()
        
        for activity in activities:
            print(f"ID: {activity.id}, Username: {activity.username}, Last Activity: {activity.last_activity_date}, Count: {activity.count}")
        set_trace()
if __name__ == '__main__':
    #create_tables()
    check_user_activities()
    app.run(debug=True)  # Add this line to run your Flask app

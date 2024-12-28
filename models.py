from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    people = db.Column(db.Integer, nullable=False)
    cars = db.Column(db.Integer, nullable=False)
    motorcycles = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Data {self.id}: {self.people} people, {self.cars} cars, {self.motorcycles} motorcycles at {self.timestamp}>'

    @classmethod
    def save_data(cls, people, cars, motorcycles):
        new_data = cls(
            people=people,
            cars=cars,
            motorcycles=motorcycles,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_data)
        db.session.commit()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nim = db.Column(db.String(20), unique=True, nullable=False)  # Added NIM column
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='mahasiswa')

    def __repr__(self):
        return f'<User {self.username}, NIM: {self.nim}, Role: {self.role}>'

    @classmethod
    def create_user(cls, nim, username, password, role='mahasiswa'):
        new_user = cls(
            nim=nim,  # Set the NIM field
            username=username,
            password=password,
            role=role
        )
        db.session.add(new_user)
        db.session.commit()

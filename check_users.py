from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    users = User.query.all()
    
    if not users:
        print("No users found in the database. Creating default admin user...")
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin"),
            role="admin"
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created!")
    else:
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"- Username: {user.username}, Email: {user.email}, Role: {user.role}")
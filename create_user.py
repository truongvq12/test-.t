from datetime import datetime
import os
from azure.cosmos import CosmosClient, exceptions

from app.dto.models import UserDTO, delete_document, insert_document, read_collection, update_document
from app.utils import format_datetime
from config import Config

client = CosmosClient(Config.COSMOS_URL, Config.COSMOS_KEY)

# Get current user from env
env_user_id = Config.USERID
env_user_name = Config.USER_NAME
env_user_email = Config.USEREMAIL
env_is_admin = Config.IS_ADMIN


def create_user():
    try:
        # Connect to the database
        database = client.get_database_client(Config.DATABASE_NAME)

        # Get the container client
        user_container = database.get_container_client("user")
        
        # Query to get all items from the container
        users = read_collection(user_container, UserDTO.collection_name, id=env_user_id)

        # Check current user exist and create
        if env_user_id not in users:
            current_datetime = format_datetime(datetime.now())
            user_document = {
                "id": env_user_id,
                "username": env_user_name,
                "email": env_user_email,
                "ai_model_id": "gpt-4-mini",
                "ai_model_display_name": "GPT-4o mini",
                "personal_projects": [],
                "created_at": current_datetime,
                "updated_at": current_datetime,
                "deleted_at": None,
                "collection_name": "user"
            }
            insert_document(user_container, user_document, UserDTO, UserDTO.collection_name)
            print("User created successfully")
            
        else:
            print("User already exist")

    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred while create user: {e.message}")
        
        
def update_user():
    try:
        # Connect to the database
        database = client.get_database_client(Config.DATABASE_NAME)

        # Get the container client
        user_container = database.get_container_client("user")
        
        # Query to get all items from the container
        users = read_collection(user_container, UserDTO.collection_name, id=env_user_id)
        
        # Check current user exist and create
        if env_user_id in users:
            user_item = users[env_user_id]
            user_item["username"] = env_user_name
            user_item["email"] = env_user_email
            
            update_document(user_container, user_item, UserDTO, UserDTO.collection_name)
            print("User updated successfully")
            
        else:
            print("User not found")

    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred while update user: {e.message}")
        
        
def delete_user():
    try:
        # Connect to the database
        database = client.get_database_client(Config.DATABASE_NAME)

        # Get the container client
        user_container = database.get_container_client("user")
        
        # Query to get all items from the container
        users = read_collection(user_container, UserDTO.collection_name, id=env_user_id)
        
        # Check current user exist and create
        if env_user_id in users:
            delete_document(user_container, env_user_id, UserDTO, UserDTO.collection_name, soft_delete=False)
            print("User deleted successfully")
            
        else:
            print("User not found")

    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred while delete user: {e.message}")


def read_users(id: str = None):
    try:
        # Connect to the database
        database = client.get_database_client(Config.DATABASE_NAME)

        # Get the container client
        user_container = database.get_container_client("user")
        
        # Query to get all items from the container
        users = read_collection(user_container, UserDTO.collection_name, id=id)
        print(users)
        
    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred while read users: {e.message}")

# create_user()
# update_user()
# delete_user()
# read_users()
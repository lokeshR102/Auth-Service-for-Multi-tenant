# db.py

import mysql.connector
from mysql.connector import Error
from flask import current_app

def get_db_connection():
    """Establish a database connection."""
    try:
        connection = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error: {e}")
        return None

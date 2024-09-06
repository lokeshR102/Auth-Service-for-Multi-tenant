# routes.py

from flask import Blueprint, request, jsonify, g
import hashlib
import json
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from flask_mail import Message
from app import mail

api_bp = Blueprint('api', __name__)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_password, provided_password):
    return stored_password == hash_password(provided_password)

def generate_tokens(user_id):
    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)
    return access_token, refresh_token

def send_email(subject, recipient, template, **kwargs):
    msg = Message(subject=subject, recipients=[recipient], html=template.format(**kwargs))
    mail.send(msg)

@api_bp.route('/signin', methods=['POST'])
def signin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    conn = g.db
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user and verify_password(user['password'], password):
        access_token, refresh_token = generate_tokens(user['id'])
        return jsonify({"access_token": access_token, "refresh_token": refresh_token}), 200
    return jsonify({"message": "Invalid credentials"}), 401

@api_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    org_name = data.get('org_name')

    conn = g.db
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
    if cursor.fetchone():
        return jsonify({"message": "User already exists"}), 400

    hashed_password = hash_password(password)
    cursor.execute("INSERT INTO User (email, password) VALUES (%s, %s)", (email, hashed_password))
    user_id = cursor.lastrowid

    cursor.execute("INSERT INTO Organisation (name) VALUES (%s)", (org_name,))
    org_id = cursor.lastrowid

    cursor.execute("INSERT INTO Role (name, org_id) VALUES (%s, %s)", ('owner', org_id))
    role_id = cursor.lastrowid

    cursor.execute("INSERT INTO Member (org_id, user_id, role_id) VALUES (%s, %s, %s)", (org_id, user_id, role_id))
    conn.commit()

    access_token, refresh_token = generate_tokens(user_id)
    #send_email('Welcome to the Platform!', email, 'Welcome {user}', user=email)

    return jsonify({"message": "User registered successfully!", "access_token": access_token, "refresh_token": refresh_token}), 201

@api_bp.route('/reset_password', methods=['POST'])
@jwt_required()
def reset_password():
    user_id = get_jwt_identity()
    data = request.get_json()
    new_password = data.get('new_password')

    conn = g.db
    cursor = conn.cursor(dictionary=True)

    hashed_password = hash_password(new_password)
    cursor.execute("UPDATE User SET password = %s WHERE id = %s", (hashed_password, user_id))
    conn.commit()
    #send_email('You have been invited!', email, 'You have been invited to join {org_name} with role {role_name}', org_name=org_id, role_name=role_name)
    return jsonify({"message": "Password updated successfully"}), 200

@api_bp.route('/invite_member', methods=['POST'])
@jwt_required()
def invite_member():
    data = request.get_json()
    email = data.get('email')
    org_id = data.get('org_id')
    role_name = data.get('role_name')

    conn = g.db
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM Organisation WHERE id = %s", (org_id,))
    if not cursor.fetchone():
        return jsonify({"message": "Organization does not exist"}), 404

    cursor.execute("SELECT id FROM Role WHERE name = %s AND org_id = %s", (role_name, org_id))
    role = cursor.fetchone()
    if not role:
        return jsonify({"message": "Role does not exist"}), 404

    cursor.execute("SELECT id FROM User WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        cursor.execute("INSERT INTO Member (org_id, user_id, role_id) VALUES (%s, %s, %s)", (org_id, user['id'], role['id']))
        conn.commit()
        #send_email('You have been invited!', email, 'You have been invited to join {org_name} with role {role_name}', org_name=org_id, role_name=role_name)
        return jsonify({"message": "Member invited successfully"}), 200

    return jsonify({"message": "User does not exist"}), 404

@api_bp.route('/delete_member/<int:member_id>', methods=['DELETE'])
@jwt_required()
def delete_member(member_id):
    conn = g.db
    cursor = conn.cursor()

    cursor.execute("DELETE FROM Member WHERE id = %s", (member_id,))
    conn.commit()

    return jsonify({"message": "Member deleted successfully"}), 200

@api_bp.route('/update_member_role/<int:member_id>', methods=['PUT'])
@jwt_required()
def update_member_role(member_id):
    data = request.get_json()
    new_role_name = data.get('role_name')

    conn = g.db
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM Role WHERE name = %s", (new_role_name,))
    new_role = cursor.fetchone()

    if not new_role:
        return jsonify({"message": "Role does not exist"}), 404

    cursor.execute("UPDATE Member SET role_id = %s WHERE id = %s", (new_role['id'], member_id))
    conn.commit()

    return jsonify({"message": "Member role updated successfully"}), 200

@api_bp.route('/stats/rolewise_users', methods=['GET'])
def rolewise_users():
    conn = g.db
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT Role.name AS role_name, COUNT(User.id) AS user_count
        FROM User
        JOIN Member ON User.id = Member.user_id
        JOIN Role ON Member.role_id = Role.id
        GROUP BY Role.name
    """)
    result = cursor.fetchall()

    return jsonify(result), 200

@api_bp.route('/stats/orgwise_members', methods=['GET'])
def orgwise_members():
    conn = g.db
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT Organisation.name AS org_name, COUNT(Member.id) AS member_count
        FROM Member
        JOIN Organisation ON Member.org_id = Organisation.id
        GROUP BY Organisation.name
    """)
    result = cursor.fetchall()

    return jsonify(result), 200

@api_bp.route('/stats/org_rolewise_users', methods=['GET'])
def org_rolewise_users():
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    status_filter = request.args.get('status')

    query = """
        SELECT Organisation.name AS org_name, Role.name AS role_name, COUNT(User.id) AS user_count
        FROM User
        JOIN Member ON User.id = Member.user_id
        JOIN Role ON Member.role_id = Role.id
        JOIN Organisation ON Member.org_id = Organisation.id
        WHERE 1=1
    """
    params = []

    if from_date:
        query += " AND User.created_at >= %s"
        params.append(from_date)
    if to_date:
        query += " AND User.created_at <= %s"
        params.append(to_date)
    if status_filter:
        query += " AND User.status = %s"
        params.append(status_filter)

    query += """
        GROUP BY Organisation.name, Role.name
    """

    conn = g.db
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query, params)
    result = cursor.fetchall()

    return jsonify(result), 200

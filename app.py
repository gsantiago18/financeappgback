from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
import psycopg2

app = Flask(__name__)
CORS(app)  # Habilita CORS para permitir el acceso desde el frontend

# Configuración de PostgreSQL
DB_CONFIG = {
    "dbname": "railway",
    "user": "postgres",
    "password": "KdilpqNrercaUrOHtZuqDirtLjibGBvY",
    "host": "viaduct.proxy.rlwy.net",
    "port": 40583
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)



@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    nombre = data.get('nombre')
    email = data.get('email')
    password = data.get('password')

    if not nombre or not email or not password:
        return jsonify({"message": "Todos los campos son obligatorios"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO usuario (nombre, email, password_hash) VALUES (%s, %s, %s) RETURNING usuario_id",
                    (nombre, email, hashed_password))
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Usuario registrado correctamente", "user_id": user_id}), 201
    except psycopg2.IntegrityError:
        return jsonify({"message": "El usuario ya existe"}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT usuario_id, nombre, password_hash FROM usuario WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        stored_hash = bytes(user[2])  # 🔹 Convertir `BYTEA` de PostgreSQL a `bytes`
        
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return jsonify({"message": "Inicio de sesión correcto", "user_id": user[0], "nombre": user[1]}), 200
    
    return jsonify({"message": "Credenciales incorrectas"}), 401

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
import psycopg2
import jwt
import datetime
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Configuración de PostgreSQL desde .env
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

SECRET_KEY = os.getenv("SECRET_KEY")

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
            token = jwt.encode(
                {"user_id":user[0], 
                 "exp":datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1) 
                 },
                "SECRET_KEY",
                algorithm="HS256"
            )
            return jsonify({"message": "Inicio de sesión correcto", "user_id": user[0], "nombre": user[1]}), 200
    
    return jsonify({"message": "Credenciales incorrectas"}), 401

@app.route('/api/categoria' , methods=['GET'])
def categorias():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_categoria, cat_nombre FROM categoria")
    categorias = cur.fetchall()
    cur.close()
    conn.close()

    categorias= [{"id":cat[0], "nombre":cat[1]} for cat in categorias]
    return jsonify(categorias)

@app.route('/api/registro/<int:usuario_id>', methods=['GET'])
def registros(usuario_id):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT 
            registro.monto,
            registro.fecha,
            c.cat_nombre,
            COALESCE(s.nombre_subct, '') AS nombre_subct,
            registro.observacion
        FROM registro
        INNER JOIN categoria c ON registro.id_categoria = c.id_categoria
        LEFT JOIN subcategoria s ON registro.id_subcategoria = s.id_subcategoria
        WHERE usuario_id = %s
    """
    params = [usuario_id,]

    from_date = request.args.get('from')
    to_date=  request.args.get('to')
    category= request.args.get('category')
    subcategory= request.args.get('subcategory')

    if from_date and to_date:
        query += " AND registro.fecha BETWEEN %s AND %s"
        params.extend([from_date, to_date])

    if category:
        query +=  " AND registro.id_categoria = %s"
        params.append(category)

    if subcategory:
        query += " AND registro.id_subcategoria = %s"  
        params.append(subcategory)  
            
    cur.execute(query, params)
    registros = cur.fetchall()
    result=[]
    for reg in registros:
        result.append({
            "monto": reg[0],
            "fecha": reg[1].strftime('%Y-%m-%d'),
            "categoria": reg[2],
            "subcategoria": reg[3],
            "observacion": reg[4]
        })
    cur.close()
    conn.close()
    return jsonify(result)    

@app.route('/api/subcategorias/<int:id_categoria>', methods=['GET'])
def subcategorias(id_categoria):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_subcategoria, nombre_subct FROM subcategoria WHERE id_categoria = %s", (id_categoria,))
    subcategorias = cur.fetchall()
    cur.close()
    conn.close()

    subcategorias_json = [{"id":sub[0], "nombre":sub[1]} for sub in subcategorias]
    return jsonify(subcategorias_json)


@app.route('/api/nuevo_gasto/<int:id_categoria>/<int:usuario_id>', defaults={'id_subcategoria': None}, methods=['POST'])
@app.route('/api/nuevo_gasto/<int:id_categoria>/<int:usuario_id>/<int:id_subcategoria>', methods=['POST'])
def nuego_gasto(id_categoria,usuario_id,id_subcategoria):
    data = request.json
    monto = data.get('monto')
    fecha = data.get('fecha')
    observacion = data.get('observacion')

    if not monto or not fecha:
        return jsonify({"message": "Todos los campos son obligatorios"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if id_subcategoria is not None:
            cur.execute("INSERT INTO registro ( monto, fecha, id_categoria,usuario_id, observacion,id_subcategoria) VALUES (%s, %s, %s, %s, %s, %s)",
                    (monto, fecha, id_categoria,usuario_id, observacion,id_subcategoria))
        else:
            cur.execute("""
                INSERT INTO registro (monto, fecha, id_categoria, usuario_id, observacion) 
                VALUES (%s, %s, %s, %s, %s)
            """, (monto, fecha, id_categoria, usuario_id, observacion))   
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Gasto registrado correctamente"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"message": "Error al registrar el gasto"}), 500



if __name__ == '__main__':
    app.run(debug=True)
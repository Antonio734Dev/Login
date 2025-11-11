import os
from flask import Flask, redirect, url_for, render_template_string, session, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from authlib.integrations.flask_client import OAuth
import requests # Authlib a veces necesita 'requests' explícitamente

# --- CONFIGURACIÓN ---

# 1. Pon tus credenciales de Google aquí
# (Es mejor usar variables de entorno, pero esto funciona para un ejemplo simple)
GOOGLE_CLIENT_ID = "TU_ID_DE_CLIENTE_VA_AQUI"
GOOGLE_CLIENT_SECRET = "TU_SECRETO_DE_CLIENTE_VA_AQUI"

# 2. Configuración de Flask
app = Flask(__name__)
# Se necesita una clave secreta para las sesiones de Flask y Flask-Login
app.secret_key = os.urandom(12) 

# 3. Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = '/' # A dónde redirigir si se necesita login

# 4. Configuración de Authlib (OAuth)
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    # Los 'scopes' definen qué información pides a Google
    client_kwargs={'scope': 'openid email profile'},
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
)

# --- MODELO DE USUARIO (Simple) ---

# Para este ejemplo, usaremos un diccionario simple como "base de datos"
# En una app real, usarías SQL, MongoDB, etc.
db_usuarios = {}

class User(UserMixin):
    """
    Clase de usuario mínima para Flask-Login.
    """
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

    @staticmethod
    def get(user_id):
        # Devuelve el objeto User si existe en nuestra "DB"
        if user_id in db_usuarios:
            user_data = db_usuarios[user_id]
            return User(user_id, user_data['name'], user_data['email'])
        return None

    @staticmethod
    def create(user_info):
        # Crea un nuevo usuario en nuestra "DB"
        user_id = user_info['id']
        db_usuarios[user_id] = user_info
        return User(user_id, user_info['name'], user_info['email'])

@login_manager.user_loader
def load_user(user_id):
    """Callback requerido por Flask-Login para cargar un usuario desde la sesión."""
    return User.get(user_id)

# --- RUTAS DE LA APLICACIÓN ---

@app.route('/')
def index():
    """
    Página principal. Sirve el HTML del frontend.
    """
    # Usamos render_template_string para mantener todo en un archivo.
    # En una app real, usarías render_template('index.html')
    return render_template_string(HTML_FRONTEND)

@app.route('/login')
def login():
    """
    Ruta para iniciar el proceso de login.
    Redirige al usuario a la página de login de Google.
    """
    # Define a dónde debe volver Google después de autorizar
    redirect_uri = url_for('auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth():
    """
    Ruta de callback. Google redirige aquí después del login.
    """
    try:
        # 1. Obtiene el token de Google
        token = google.authorize_access_token()
    except Exception as e:
        print(f"Error al obtener token: {e}")
        return redirect(url_for('index'))

    # 2. Pide la información del usuario a Google usando el token
    # 'userinfo_endpoint' se usa aquí
    resp = google.get('userinfo')
    user_info = resp.json()

    # 3. Busca o crea el usuario en nuestra "base de datos"
    user_id = user_info['id']
    user = User.get(user_id)
    if user is None:
        user = User.create(user_info)

    # 4. Inicia la sesión del usuario en nuestro sistema
    login_user(user)

    # 5. Redirige de vuelta al inicio
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Cierra la sesión del usuario."""
    logout_user()
    return redirect(url_for('index'))


# --- API (Para que el Frontend consulte) ---

@app.route('/api/profile')
def get_profile():
    """
    Una ruta de API que el frontend (React, Vue, JS) puede usar
    para obtener los datos del usuario actual.
    """
    if current_user.is_authenticated:
        # Si el usuario está logueado, devuelve sus datos
        return jsonify({
            'logged_in': True,
            'user': {
                'name': current_user.name,
                'email': current_user.email,
            }
        })
    else:
        # Si no, informa que no hay nadie logueado
        return jsonify({'logged_in': False})

# --- Plantilla HTML ---
# (Se pone aquí para que todo esté en un solo archivo)

HTML_FRONTEND = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login con Google</title>
    <style>
        body { font-family: Arial, sans-serif; display: grid; place-items: center; min-height: 80vh; }
        .container { padding: 20px; border: 1px solid #ccc; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .button { display: inline-block; padding: 10px 20px; background-color: #4285F4; color: white; text-decoration: none; border-radius: 5px; }
        .logout { background-color: #db4437; }
        #loading { display: block; }
        #logged-in, #logged-out { display: none; }
    </style>
</head>
<body>
    <div class="container">
        
        <div id="loading">
            <p>Cargando...</p>
        </div>

        <div id="logged-out">
            <h1>Bienvenido</h1>
            <p>Por favor, inicia sesión para continuar.</p>
            <a href="/login" class="button">Login con Google</a>
        </div>

        <div id="logged-in">
            <h1>Hola, <span id="user-name"></span></h1>
            <p>Email: <span id="user-email"></span></p>
            <a href="/logout" class="button logout">Cerrar Sesión</a>
        </div>

    </div>

    <script>
        // Este script se ejecuta cuando la página carga
        // Llama a nuestra API para ver si ya hay una sesión activa
        document.addEventListener('DOMContentLoaded', () => {
            fetch('/api/profile')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('loading').style.display = 'none';

                    if (data.logged_in) {
                        // Si está logueado, muestra sus datos
                        document.getElementById('logged-in').style.display = 'block';
                        document.getElementById('user-name').innerText = data.user.name;
                        document.getElementById('user-email').innerText = data.user.email;
                    } else {
                        // Si no está logueado, muestra el botón de login
                        document.getElementById('logged-out').style.display = 'block';
                    }
                });
        });
    </script>
</body>
</html>
"""

# --- Ejecutar la App ---
if __name__ == '__main__':
    # Usamos 127.0.0.1 en lugar de localhost para ser explícitos
    # (ya que así lo configuramos en Google)
    app.run(host='127.0.0.1', port=5000, debug=True)
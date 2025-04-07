from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB por imagem
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Criação do banco de dados se não existir
def init_db():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                codigo TEXT NOT NULL,
                descricao TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS imagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                caminho TEXT NOT NULL,
                FOREIGN KEY (produto_id) REFERENCES produtos (id)
            )
        ''')
        conn.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Inicialização
init_db()
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Rota principal
@app.route('/')
def index():
    search = request.args.get('search', '').strip()
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        if search:
            cursor.execute("""
                SELECT * FROM produtos
                WHERE nome LIKE ? OR codigo LIKE ?
            """, (f'%{search}%', f'%{search}%'))
        else:
            cursor.execute("SELECT * FROM produtos")
        produtos = cursor.fetchall()

        # Buscar imagens
        produtos_com_imagens = []
        for p in produtos:
            cursor.execute("SELECT id, caminho FROM imagens WHERE produto_id=?", (p[0],))
            imagens = cursor.fetchall()
            produtos_com_imagens.append((p, imagens))

    return render_template('index.html', produtos=produtos_com_imagens, search=search)

# Cadastro de novo produto
@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        codigo = request.form['codigo'].strip()
        descricao = request.form['descricao'].strip()
        fotos = request.files.getlist('fotos[]')

        if len(fotos) > 10:
            return "Limite de até 10 imagens por produto.", 400

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO produtos (nome, codigo, descricao)
                VALUES (?, ?, ?)
            ''', (nome, codigo, descricao))
            produto_id = cursor.lastrowid

            for foto in fotos:
                if foto and allowed_file(foto.filename):
                    ext = os.path.splitext(foto.filename)[1]
                    filename = f"{uuid.uuid4().hex}{ext}"
                    caminho = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    foto.save(caminho)
                    cursor.execute('''
                        INSERT INTO imagens (produto_id, caminho) VALUES (?, ?)
                    ''', (produto_id, filename))

            conn.commit()
        return redirect(url_for('index'))

    return render_template('form.html', produto=None, imagens=[])

# Edição de produto
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        if request.method == 'POST':
            nome = request.form['nome'].strip()
            codigo = request.form['codigo'].strip()
            descricao = request.form['descricao'].strip()
            novas_fotos = request.files.getlist('fotos[]')

            cursor.execute('''
                UPDATE produtos SET nome=?, codigo=?, descricao=? WHERE id=?
            ''', (nome, codigo, descricao, id))

            for foto in novas_fotos:
                if foto and allowed_file(foto.filename):
                    ext = os.path.splitext(foto.filename)[1]
                    filename = f"{uuid.uuid4().hex}{ext}"
                    caminho = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    foto.save(caminho)
                    cursor.execute('''
                        INSERT INTO imagens (produto_id, caminho) VALUES (?, ?)
                    ''', (id, filename))

            conn.commit()
            return redirect(url_for('index'))

        cursor.execute("SELECT * FROM produtos WHERE id=?", (id,))
        produto = cursor.fetchone()

        cursor.execute("SELECT id, caminho FROM imagens WHERE produto_id=?", (id,))
        imagens = cursor.fetchall()

    return render_template('form.html', produto=produto, imagens=imagens)

# Deletar produto
@app.route('/deletar/<int:id>')
def deletar(id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT caminho FROM imagens WHERE produto_id=?", (id,))
        imagens = cursor.fetchall()
        for img in imagens:
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], img[0])
            if os.path.exists(caminho):
                os.remove(caminho)

        cursor.execute("DELETE FROM imagens WHERE produto_id=?", (id,))
        cursor.execute("DELETE FROM produtos WHERE id=?", (id,))
        conn.commit()

    return redirect(url_for('index'))

# Deletar imagem individual
@app.route('/excluir-imagem/<int:id>')
def excluir_imagem(id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT caminho, produto_id FROM imagens WHERE id=?", (id,))
        imagem = cursor.fetchone()
        if imagem:
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], imagem[0])
            if os.path.exists(caminho):
                os.remove(caminho)
            cursor.execute("DELETE FROM imagens WHERE id=?", (id,))
            conn.commit()
        return redirect(url_for('editar', id=imagem[1]))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

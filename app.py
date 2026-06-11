from dotenv import load_dotenv
from flask import Flask, render_template, request

from weather_service import buscar_clima_por_cidade
from database import init_db # Importar a função init_db

load_dotenv()

app = Flask(__name__)

# Inicializa o banco de dados ao iniciar a aplicação
init_db()


@app.route("/", methods=["GET"])
def home():
    cidade = request.args.get("cidade", "").strip()
    weather = None
    error = None

    if cidade:
        result = buscar_clima_por_cidade(cidade)
        if result["error"]:
            error = result["message"]
        else:
            weather = result["data"]

    return render_template(
        "index.html",
        weather=weather,
        error=error,
        cidade=cidade
    )

if __name__ == "__main__":
    app.run(debug=True)

"""Run the diabetes coach locally: python run_web.py"""

from webapp import create_app

app = create_app()

if __name__ == "__main__":
    # host=0.0.0.0 so you can open it from your iPhone on the same Wi-Fi
    app.run(host="0.0.0.0", port=5070, debug=True)

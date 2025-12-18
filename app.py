from app import create_app

# Initialize Flask app via factory pattern
app = create_app()

if __name__ == '__main__':
    # ✅ Enable debug mode only in development
    app.run(host='0.0.0.0', port=5000, debug=True)

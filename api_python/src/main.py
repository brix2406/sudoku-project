from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
api = Api(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day","30 per hour"],
    storage_uri="memory://",
)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, host="0.0.0.0") 

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class SudokuImageReceiver(Resource):
    decorators = [limiter.limit("10 per minute")]

    def post(self):
        app.logger.info(">>> Received a POST request at /solve-image")

        if 'image' not in request.files:
            app.logger.warning("<<< Request failed: No 'image' key in payload")
            return {'error': 'No image provided in request payload. Key must be "image".'}, 400
        
        file = request.files['image']
        
        if file.filename == '':
            app.logger.warning("<<< Request failed: No file selected")
            return {'error': 'No file selected'}, 400
        
        if file and allowed_file(file.filename):
            image_bytes = file.read()
            file_size = len(image_bytes)
            
            app.logger.info(f"<<< Success! Extracted image: '{file.filename}' ({file_size} bytes)")
            
            return {
                'message': 'Image successfully received by the API (NATS routing pending)',
                'filename': file.filename,
                'size_bytes': file_size
            }, 200
                
        app.logger.warning(f"<<< Request failed: Invalid file type ({file.filename})")
        return {'error': 'Invalid file type. Only PNG and JPG are allowed.'}, 400

api.add_resource(SudokuImageReceiver, '/solve-image')

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True)
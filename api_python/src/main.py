import asyncio
from flask import Flask, request
from flask_restful import Resource, Api
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import your dedicated NATS bridge
from nats_api import process_image_and_solve

app = Flask(__name__)
api = Api(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day", "30 per hour"],
    storage_uri="memory://",
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class SudokuImageReceiver(Resource):
    decorators = [limiter.limit("10 per minute")]

    # Notice this is back to a standard, synchronous `def`!
    def post(self):
        app.logger.info(">>> Received a POST request at /solve-image")

        if 'image' not in request.files:
            return {'error': 'No image provided.'}, 400
        
        file = request.files['image']
        if file.filename == '' or not allowed_file(file.filename):
            return {'error': 'Invalid file type.'}, 400
        
        # Extract the raw bytes
        image_bytes = file.read()
        app.logger.info(f"<<< Extracted '{file.filename}'. Handing off to NATS API bridge...")
        
        try:
            n = int(request.form.get("n", 3))
            k = int(request.form.get("k", 3))
            app.logger.info(f"  Grid dimensions: n={n}, k={k}")
            results = asyncio.run(process_image_and_solve(image_bytes, n, k))

            app.logger.info("<<< Pipeline Complete! Returning solved puzzle.")
            return {
                'message': 'Sudoku successfully extracted and solved!',
                'filename': file.filename,
                'original_board': results['original_board'],
                'solved_board': results['solved_board']
            }, 200
            
        except ValueError as ve:
            app.logger.warning(f"<<< Pipeline Error: {ve}")
            return {'error': str(ve)}, 422
            
        except TimeoutError as te:
            app.logger.error(f"<<< NATS Timeout: {te}")
            return {'error': str(te)}, 504
            
        except Exception as e:
            app.logger.error(f"<<< Unexpected Server Error: {e}")
            return {'error': 'An internal server error occurred.'}, 500

api.add_resource(SudokuImageReceiver, '/solve-image')

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, host="0.0.0.0")
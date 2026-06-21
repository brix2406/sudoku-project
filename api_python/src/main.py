import asyncio
import re
from datetime import datetime

from flask import Flask, request
from flask_restful import Resource, Api
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from nats_api import process_image_and_solve, process_manual_and_solve, get_nats_status

from flask_cors import CORS

app = Flask(__name__)
api = Api(app)
CORS(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day", "30 per hour"],
    storage_uri="memory://",
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_sudoku_string(value):
    """Parse a Sudoku{(k,n)(cells...)} string into (k, n, board)."""
    match = re.match(r'^Sudoku\{\((\d+),(\d+)\)\((.*)\)\}$', value.strip())
    if not match:
        raise ValueError('Invalid sudoku string format.')

    k = int(match.group(1))
    n = int(match.group(2))
    raw_cells = match.group(3)

    if k < 1 or n < 1:
        raise ValueError('Invalid dimensions: k and n must be positive.')

    board_size = k * n
    expected_cells = board_size * board_size
    cells = raw_cells.split(',') if raw_cells else []

    if len(cells) != expected_cells:
        raise ValueError(
            f'Expected {expected_cells} cells for a {board_size}×{board_size} board, got {len(cells)}.'
        )

    max_value = n * n
    board = []
    for row_index in range(board_size):
        row = []
        for col_index in range(board_size):
            cell = cells[row_index * board_size + col_index]
            if cell in ('', '.', '0'):
                row.append('.')
            else:
                val = int(cell)
                if val < 1 or val > max_value:
                    raise ValueError(f'Cell value {val} at ({row_index},{col_index}) exceeds max value {max_value}.')
                row.append(str(val))
        board.append(row)

    return k, n, board

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
            

        except RuntimeError as re_err:
            app.logger.error(f"<<< Service Layer Error: {re_err}")
            return {'error': str(re_err)}, 422
        except TimeoutError as te:
            app.logger.error(f"<<< NATS Timeout: {te}")
            return {'error': str(te)}, 504
            
        except Exception as e:
            app.logger.error(f"<<< Unexpected Server Error: {e}")
            return {'error': 'An internal server error occurred.'}, 500

class SudokuManualReceiver(Resource):
    decorators = [limiter.limit("10 per minute")]

    def post(self):
        app.logger.info(">>> Received a POST request at /manual_solve")

        data = request.get_json(silent=True)
        if not data or 'sudoku_string' not in data:
            return {'error': 'No sudoku string provided.'}, 400

        try:
            k, n, board = parse_sudoku_string(data['sudoku_string'])
            app.logger.info(f"  Parsed manual sudoku: k={k}, n={n}")

            results = asyncio.run(process_manual_and_solve(k, n, board))

            app.logger.info("<<< Manual solve complete! Returning solved puzzle.")
            return {
                'message': 'Sudoku successfully solved!',
                'original_board': results['original_board'],
                'solved_board': results['solved_board'],
            }, 200

        except ValueError as ve:
            app.logger.warning(f"<<< Parse/Solver Error: {ve}")
            return {'error': str(ve)}, 422

        except TimeoutError as te:
            app.logger.error(f"<<< NATS Timeout: {te}")
            return {'error': str(te)}, 504

        except RuntimeError as re_err:
            app.logger.error(f"<<< Service Layer Error: {re_err}")
            return {'error': str(re_err)}, 502

        except Exception as e:
            app.logger.error(f"<<< Unexpected Server Error: {e}")
            return {'error': 'An internal server error occurred.'}, 500


class StatusReceiver(Resource):
    decorators = [limiter.exempt]
    def get(self):
        try:
            result = asyncio.run(get_nats_status())
        except Exception:
            result = {
                'serviceStatus': 'offline',
                'workerStatus': 'disconnected',
                'latencyMs': 0,
                'queueDepth': 0,
            }
        result['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        return result, 200

api.add_resource(SudokuImageReceiver, '/solve-image', '/ocr_solve')
api.add_resource(StatusReceiver, '/status')
api.add_resource(SudokuManualReceiver, '/manual_solve')

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, host="0.0.0.0")
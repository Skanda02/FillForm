"""Flask application entry point for FillForm."""

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS

from routes.api import api_bp
from services.analyzer import analyze_text
from services.autofill import build_autofill_profile
from services.parser import parse_submission_input
from services.reminders import build_reminder_plan


HOME_TEMPLATE = """
<!doctype html>
<html lang="en">
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title>FillForm</title>
		<style>
			body { font-family: system-ui, sans-serif; margin: 0; background: #f6f7fb; color: #111827; }
			.wrap { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
			.card { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); }
			label { display: block; font-weight: 600; margin: 16px 0 8px; }
			textarea, input[type="file"] { width: 100%; box-sizing: border-box; }
			textarea { min-height: 180px; padding: 12px; border-radius: 12px; border: 1px solid #d1d5db; }
			button { margin-top: 16px; padding: 12px 18px; border: 0; border-radius: 12px; background: #111827; color: white; font-weight: 700; cursor: pointer; }
			pre { white-space: pre-wrap; word-break: break-word; background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 12px; overflow: auto; }
			.hint { color: #6b7280; }
		</style>
	</head>
	<body>
		<div class="wrap">
			<div class="card">
				<h1>FillForm</h1>
				<p class="hint">Paste text or upload a PDF to extract content, analyze it, and generate reminders and autofill hints.</p>
				<label for="text">Text input</label>
				<textarea id="text" placeholder="Paste a form, document, or notes here..."></textarea>
				<label for="file">PDF input</label>
				<input id="file" type="file" accept="application/pdf" />
				<button id="submit">Analyze input</button>
				<h2>Result</h2>
				<pre id="output">Submit text or a PDF to see the response here.</pre>
			</div>
		</div>
		<script>
			const button = document.getElementById('submit');
			const output = document.getElementById('output');
			button.addEventListener('click', async () => {
				const formData = new FormData();
				const text = document.getElementById('text').value;
				const file = document.getElementById('file').files[0];
				if (text) formData.append('text', text);
				if (file) formData.append('file', file);
				output.textContent = 'Processing...';
				try {
					const response = await fetch('/analyze', { method: 'POST', body: formData });
					const result = await response.json();
					output.textContent = JSON.stringify(result, null, 2);
				} catch (error) {
					output.textContent = String(error);
				}
			});
		</script>
	</body>
</html>
"""


def create_app() -> Flask:
		app = Flask(__name__)
		CORS(app)
		app.register_blueprint(api_bp)

		@app.get("/")
		def home() -> str:
				return render_template_string(HOME_TEMPLATE)

		@app.post("/analyze")
		def analyze() -> tuple[object, int]:
				parsed = parse_submission_input(request)
				analysis = analyze_text(parsed["text"])
				autofill_profile = build_autofill_profile(parsed["text"])
				reminder_plan = build_reminder_plan(analysis.get("deadline_candidates", []))
				return jsonify(
						{
								"input": parsed,
								"analysis": analysis,
								"autofill": autofill_profile,
								"reminders": reminder_plan,
						}
				), 200

		return app


app = create_app()


if __name__ == "__main__":
		app.run(debug=True)

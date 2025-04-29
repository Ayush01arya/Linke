from flask import Flask, request, jsonify, render_template
from googlesearch import search
import re
import time
import random
import threading
import uuid

app = Flask(__name__)

# Store search results with unique IDs
search_results = {}
search_status = {}


def search_linkedin_posts(search_id, keyword, description, num_results=10):
    """
    Search for LinkedIn posts related to a keyword and description.

    Args:
        search_id (str): Unique ID for this search request
        keyword (str): The main topic to search for
        description (str): Additional context to narrow the search
        num_results (int): Maximum number of results to return
    """
    # Define queries specifically targeting posts/updates
    queries = [
        f'site:linkedin.com/posts "{keyword}" "{description}"',
        f'site:linkedin.com/feed/update "{keyword}" "{description}"',
        f'inurl:linkedin.com/posts "{keyword}" "{description}"',
    ]

    post_urls = []
    post_pattern = re.compile(r'(https?://.*?linkedin\.com/(posts|feed/update)/.*?)(?:\s|$)')

    search_status[search_id] = {
        'status': 'in_progress',
        'message': 'Search started',
        'progress': 0,
        'total_queries': len(queries)
    }

    for i, query in enumerate(queries):
        try:
            search_status[search_id]['message'] = f"Searching with query: {query}"
            search_status[search_id]['progress'] = (i / len(queries)) * 100

            for url in search(query, num_results=10):
                # Extract only post URLs using regex
                matches = post_pattern.findall(url)
                if matches:
                    post_url = matches[0][0]
                    if post_url not in post_urls:
                        post_urls.append(post_url)

                        # Update results in real-time
                        search_results[search_id] = post_urls.copy()

                        if len(post_urls) >= num_results:
                            search_status[search_id] = {
                                'status': 'completed',
                                'message': 'Search completed successfully',
                                'progress': 100
                            }
                            return

                # Add a small delay to avoid getting blocked
                time.sleep(random.uniform(1, 3))
        except Exception as e:
            search_status[search_id]['message'] = f"Error during search: {str(e)}"
            # Continue with next query if one fails
            continue

    # If no results found and reached here, try with broader search
    if not post_urls:
        search_status[search_id]['message'] = "Trying broader search..."

        try:
            broader_query = f'site:linkedin.com/posts "{keyword}"'
            for url in search(broader_query, num_results=10):
                matches = post_pattern.findall(url)
                if matches:
                    post_url = matches[0][0]
                    if post_url not in post_urls:
                        post_urls.append(post_url)
                        search_results[search_id] = post_urls.copy()

                        if len(post_urls) >= num_results:
                            break

                time.sleep(random.uniform(1, 3))
        except Exception as e:
            search_status[search_id]['message'] += f" Error in broader search: {str(e)}"

    search_status[search_id] = {
        'status': 'completed',
        'message': 'Search completed' if post_urls else 'No posts found',
        'progress': 100
    }
    search_results[search_id] = post_urls


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.json
    keyword = data.get('keyword', '')
    description = data.get('description', '')
    num_results = int(data.get('num_results', 10))

    if not keyword:
        return jsonify({'error': 'Keyword is required'}), 400

    # Generate unique ID for this search
    search_id = str(uuid.uuid4())

    # Initialize search results
    search_results[search_id] = []

    # Start search in a separate thread
    thread = threading.Thread(
        target=search_linkedin_posts,
        args=(search_id, keyword, description, num_results)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'search_id': search_id,
        'message': 'Search started'
    })


@app.route('/api/search/<search_id>/status', methods=['GET'])
def get_search_status(search_id):
    if search_id not in search_status:
        return jsonify({'error': 'Invalid search ID'}), 404

    return jsonify(search_status[search_id])


@app.route('/api/search/<search_id>/results', methods=['GET'])
def get_search_results(search_id):
    if search_id not in search_results:
        return jsonify({'error': 'Invalid search ID'}), 404

    return jsonify({
        'results': search_results[search_id],
        'count': len(search_results[search_id])
    })


# Clean up old search results (could be implemented with a scheduler)
@app.route('/api/cleanup', methods=['POST'])
def cleanup_old_searches():
    # In a production environment, you would implement proper cleanup logic
    search_results.clear()
    search_status.clear()
    return jsonify({'message': 'Cleanup completed'})


if __name__ == '__main__':
    app.run(debug=True)

import logging
import json
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from jinja2 import Template
import plotly.graph_objects as go
import plotly.express as px
from pydantic import BaseModel
from typing import Dict
from get_stats import get_stats_from_label_studio

logger = logging.getLogger('uvicorn')

app = FastAPI()

html_template = Template("""
<!DOCTYPE html>
<html>
<head>
    <title>Bar Charts</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            background-color: #f5f5f5;
        }
        .row-container {
            width: 80%;
            margin: 20px 0;
            padding: 10px;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .row-container:hover {
            transform: scale(1.01);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
        }
        .row-title {
            font-size: 1.5em;
            font-weight: bold;
            margin: 10px 0;
            text-align: center;
        }
        .chart-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
        }
        .chart {
            text-align: center;
            padding: 10px;
            box-sizing: border-box;
            width: 100%;
        }
        .chart-caption {
            font-size: 1.2em;
            font-weight: bold;
            margin: 5px 0;
        }
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            const observer = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const plotElement = entry.target;
                        const plotData = JSON.parse(plotElement.getAttribute('data-plot'));
                        Plotly.newPlot(plotElement, plotData.data, plotData.layout);
                        observer.unobserve(plotElement);
                    }
                });
            }, { threshold: 0.1 });

            document.querySelectorAll('.plotly-plot').forEach(plotElement => {
                observer.observe(plotElement);
            });
        });
    </script>
</head>
<body>
    {% for row in charts %}
    <div class="row-container">
        <div class="row-title">{{ row.name }}</div>
        <div class="chart-container">
            {% for plot in row.plots %}
            <div class="chart">
                <div class="chart-caption">{{ plot.caption }}</div>
                <div class="plotly-plot" data-plot='{{ plot.json | safe }}' style="height: 400px;"></div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
</body>
</html>
""")


def create_bar_chart(data):
    names = list(data.keys())
    values = list(data.values())
    colors = px.colors.qualitative.Plotly

    fig = go.Figure(go.Bar(
        x=names,
        y=values,
        marker_color=colors[:len(names)]  # Cycle through the color list
    ))
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), xaxis=dict(tickfont=dict(size=20)))

    return json.dumps(fig.to_plotly_json())


def _load_stats() -> Dict:
    if not os.path.exists('stats.json'):
        return {}
    with open('stats.json', 'r') as f:
        return json.load(f)


def _save_stats(project, stats):
    curr_stats = _load_stats()

    curr_stats[project] = stats
    # Save stats to the file
    with open('stats.json', 'w') as f:
        json.dump(curr_stats, f)


class WebhookPayload(BaseModel):
    action: str
    project: Dict


@app.post('/webhook')
def webhook(input: WebhookPayload):

    logger.info(f"Received webhook: {input}")
    if input.action == "ANNOTATION_CREATED":
        stats = get_stats_from_label_studio(input.project['id'])
        _save_stats(input.project['title'], stats)


@app.get("/", response_class=HTMLResponse)
def index():

    stats = _load_stats()

    charts = []
    for project_title, project_data in sorted(stats.items()):
        row = {'name': f'Project: {project_title}', 'plots': []}
        for tag_name, tag_data in sorted(project_data.items()):
            json_plot = create_bar_chart(tag_data)
            row['plots'].append({'caption': tag_name, 'json': json_plot})
        charts.append(row)

    return html_template.render(charts=charts)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4321)

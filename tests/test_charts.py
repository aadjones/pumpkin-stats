import pandas as pd

from modules import charts

df = pd.DataFrame({"date": ["2024-01-01", "2024-01-02"], "anxiety": [4, 5]})


def test_line_chart():
    fig = charts.line_chart(df, "anxiety", "#000")

    # Plotly figure: extract y data
    assert fig.data[0].y.tolist() == [4, 5]

# ============================================================================
# File: dashboard_card_template.py
# ============================================================================

def build_card(card):

    return f"""
<div class="card">

    <div class="country">
        {card["country"]}
    </div>

    <div class="title">
        {card["title"]}
    </div>

    <div class="value">
        {card["value"]}
        <span>{card["unit"]}</span>
    </div>

    <div class="date">
        {card["date"]}
    </div>

    <div class="change">
        {card["change"]}
    </div>

</div>
"""

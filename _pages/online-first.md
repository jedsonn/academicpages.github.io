---
layout: default
title: Online First Journal Updates
permalink: /online-first/
---

<section class="online-first">
  <h1>{{ page.title }}</h1>
  <p>This dashboard aggregates recently accepted ("online first") papers from leading finance and accounting journals. Run <code>python scripts/online_first.py</code> to refresh the feed before publishing the site. If you do not have network access, run <code>python scripts/online_first.py --offline</code> to load the demonstration dataset bundled with the repository.</p>

  {% assign dataset = site.data.online_first %}
  {% assign entries = dataset.entries %}
  {% if dataset.updated_at %}
    <p><strong>Last updated:</strong> {{ dataset.updated_at | date: "%B %d, %Y %H:%M %Z" }}</p>
  {% endif %}

  {% if entries and entries.size > 0 %}
    <div class="table-responsive">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Title</th>
            <th>Journal</th>
            <th>Authors</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {% for entry in entries %}
            <tr>
              <td>{{ forloop.index }}</td>
              <td><a href="{{ entry.url }}">{{ entry.title }}</a></td>
              <td>
                {% if entry.source %}
                  <abbr title="{{ entry.source }}">{{ entry.journal }}</abbr>
                {% else %}
                  {{ entry.journal }}
                {% endif %}
              </td>
              <td>{{ entry.authors }}</td>
              <td>{{ entry.date }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% else %}
    <p>No articles have been collected yet. Run the update script to populate this table.</p>
  {% endif %}

  {% if dataset.errors %}
    <div class="notice--warning">
      <h2>Scraper notes</h2>
      <ul>
        {% for error in dataset.errors %}
          <li>{{ error }}</li>
        {% endfor %}
      </ul>
    </div>
  {% endif %}
</section>

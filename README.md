# Bad Grocery App

A small Flask-based web app for importing and searching grocery data.

**Prerequisites**
- **Python:** 3.12
- **pip**: Python package installer

## Quick Setup 

**using Windows Command Prompt**

1. Create and activate a virtual environment

```cmd
python -m venv venv
.\venv\Scripts\activate
```

2. Install dependencies

```cmd
pip install -r requirements.txt
```

3. Configure (optional)
- Edit [config.xml](config.xml) if you need to change application settings.

4. Run the app

```cmd
python app.py
```

## Information

The app typically serves the UI routes found in the templates folder (the Import and Search pages, for example).

**Importing sample data**
- A sample CSV is provided at [sample_data.csv](sample_data.csv). Use the app's Import page (see [templates/import.html](templates/import.html)) to load it.

**Project files**
- [app.py](app.py): application entrypoint
- [config.xml](config.xml): app configuration
- [database.py](database.py): database helper / connection code
- [models.py](models.py): data models
- [requirements.txt](requirements.txt): Python dependencies
- [sample_data.csv](sample_data.csv): example data to import
- [templates/](templates): HTML templates used by the app

## Other

**Development notes & next steps**
- To run in development mode you can set environment variables or edit `app.py` as needed.

**License**
- Fully proprietary code. All rights reserved.
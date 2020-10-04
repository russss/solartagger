from xml.etree import ElementTree
from starlette.applications import Starlette
from starlette.config import Config
from starlette.templating import Jinja2Templates
from starlette.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from databases import Database
import json

config = Config(".env")
oauth = OAuth(config)

oauth.register(name="openstreetmap",
               request_token_url="https://www.openstreetmap.org/oauth/request_token",
               access_token_url="https://www.openstreetmap.org/oauth/access_token",
               authorize_url="https://www.openstreetmap.org/oauth/authorize",
               api_base_url="https://api.openstreetmap.org/api/0.6/")

DEBUG = config('DEBUG', cast=bool, default=False)
DATABASE_URL = config('DATABASE_URL')

database = Database(DATABASE_URL)

templates = Jinja2Templates(directory='templates')

app = Starlette(debug=DEBUG, on_startup=[database.connect], on_shutdown=[database.disconnect],
                routes=[Mount('/static', app=StaticFiles(directory='static'), name="static")])
app.add_middleware(SessionMiddleware, secret_key=config.get("SECRET_KEY"))


async def query(query, **kwargs):
    return await database.execute(query=query, values=kwargs)


async def get_user(request):
    if not request.session.get('user_id'):
        return None
    return await database.fetch_one(query="SELECT * FROM solartag.users WHERE id = :id",
                                    values={'id':request.session['user_id']})


@app.route("/login")
async def login(request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/")

    osm = oauth.create_client('openstreetmap')
    redirect_uri = request.url_for("authorize")
    return await osm.authorize_redirect(request, redirect_uri)


@app.route('/auth')
async def authorize(request):
    osm = oauth.create_client('openstreetmap')
    token = await osm.authorize_access_token(request)
    res = await osm.get("user/details", token=token)
    tree = ElementTree.fromstring(res.text)
    user = tree.find('user')
    user_id = int(user.get('id'))

    request.session['user_id'] = user_id

    await query("""INSERT INTO solartag.users(id, display_name, token)
                    VALUES (:id, :display_name, :token)
                    ON CONFLICT (id) DO UPDATE SET display_name=:display_name, token=:token""",
                id=user_id, display_name=user.get('display_name'), token=json.dumps(token))
    return RedirectResponse(url="/")


@app.route('/logout')
async def logout(request):
    del request.session['user_id']
    return RedirectResponse(url="/")


@app.route('/next', methods=['POST'])
async def next(request):
    if not request.session.get("user_id"):
        raise HTTPException(403)

    data = await request.json()
    if data.get('osm_id'):
        if data['action'] == 'skip':
            await query("""INSERT INTO solartag.results(osm_id, user_id, skip_reason)
                            VALUES (:osm_id, :user_id, :skip_reason)""",
                        osm_id=data['osm_id'], user_id=request.session['user_id'],
                        skip_reason=data['skip_reason'])
        elif data['action'] == 'add':
            await query("""INSERT INTO solartag.results(osm_id, user_id, module_count)
                            VALUES (:osm_id, :user_id, :module_count)""",
                        osm_id=data['osm_id'], user_id=request.session['user_id'],
                        module_count=data['module_count'])

    q = """SELECT candidates.osm_id,
                    ST_X(ST_Transform(geometry, 4326)) AS lon,
                    ST_Y(ST_Transform(geometry, 4326)) AS lat
                FROM solartag.candidates
                LEFT OUTER JOIN solartag.results ON candidates.osm_id = results.osm_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM solartag.results
                    WHERE osm_id = candidates.osm_id
                    AND user_id = :user_id)
                GROUP BY candidates.osm_id, candidates.geometry
                HAVING count(results) < 3
                ORDER BY osm_id DESC
                LIMIT 1"""

    point = await database.fetch_one(q, {'user_id': request.session['user_id']})
    surrounding = await database.fetch_all("""SELECT ST_X(ST_Transform(geometry, 4326)) AS lon,
                                                     ST_Y(ST_Transform(geometry, 4326)) AS lat
                                                FROM solartag.candidates
                                                WHERE ST_Buffer(
                                                    (SELECT geometry FROM solartag.candidates
                                                        WHERE osm_id = :id), 50) && geometry
                                                AND osm_id != :id""",
                                           {'id': point['osm_id']})

    surrounding = [[s['lat'], s['lon']] for s in surrounding]
    return JSONResponse({'osm_id': point['osm_id'], 'location': [point['lat'], point['lon']],
                        'surrounding': surrounding})


@app.route('/')
async def main(request):
    user = await get_user(request)
    return templates.TemplateResponse('index.html', {'request': request, 'user': user})

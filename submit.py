import asyncio
from osmapi import OsmApi
from main import database, config


async def main():
    osm = OsmApi(username=config.get("OSM_SUBMIT_USER"), password=config.get("OSM_SUBMIT_PASSWORD"))

    print("Connecting...")
    await database.connect()
    print("Updating materialised view...")
    await database.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY solartag.candidates")
    print("Fetching nodes...")
    res = await database.fetch_all("""SELECT results.osm_id, array_agg(results.user_id) AS users,
                                    solartag.int_decision_value(module_count) AS modules
                       FROM solartag.results, solartag.candidates
                       WHERE results.osm_id = candidates.osm_id
                       GROUP BY results.osm_id
                       HAVING solartag.int_decision(module_count) = true
                        AND solartag.int_decision_value(module_count) IS NOT NULL
                       ORDER BY results.osm_id DESC
                       LIMIT 100""")

    users = set()
    for row in res:
        users |= set(row['users'])

    if len(list(res)) < 10:
        print("Fewer than 10 new changes, not submitting.")
        return

    print("Creating changeset...")
    osm.ChangesetCreate({"contributor_ids": ";".join(map(str, users)),
                         "source": "https://solartagger.russss.dev",
                         "comment": "Add generator:solar:modules tag",
                         "bot": "yes",
                         "imagery_used": "Bing"
                         })
    for row in res:
        node = osm.NodeGet(row['osm_id'])
        if 'generator:solar:modules' in node['tag']:
            print("Tag already exists for node", node['id'])
            continue
        node['tag']['generator:solar:modules'] = str(row['modules'])
        osm.NodeUpdate(node)

    osm.ChangesetClose()
    print("Done")

asyncio.run(main())

import requests
import time
import signal

session = requests.Session()
def rearmSession():
    print("rearm session")
    session.headers["User-Agent"] = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:99.0) Gecko/20100101 Firefox/99.0"
    session.get("https://www.vinted.fr")


def seekArticle(**kwargs):
    if "is_for_swap" not in kwargs:
        kwargs["is_for_swap"] = 0

    if "order" not in kwargs:
        kwargs["order"] = "newest_first"

    if "page" not in kwargs:
        kwargs["page"] = 1

    if "per_page" not in kwargs:
        kwargs["per_page"] = 10

    #print(kwargs)
    while True:
        # default user agent is filtered
        res = session.get("https://www.vinted.fr/api/v2/catalog/items", params=kwargs)
        #print(res.request.headers)
        if res.status_code == 200:
            return res.json()

        #print(res.status_code)
        print("request fail, waiting 250ms before continue")
        time.sleep(0.25)
        rearmSession()


interrupted = False
def signal_handler(signal, frame):
    global interrupted
    interrupted = True

signal.signal(signal.SIGINT, signal_handler)

REQ_PARAMS = {
    "catalog_ids": "257,76", # jeans homme + hauts et tee-shirts homme, voir ici : https://www.vinted.fr/api/v2/catalogs
}

latest_id = -1
while not interrupted:
    data = seekArticle(**REQ_PARAMS)
    new_latest_id = data["items"][0]["id"]
    #print("latest_id =", latest_id, ", new_latest_id =", new_latest_id) # increase not guaranteed, dup check might be needed
    if latest_id != -1:        
        p = 1
        while True:
            for e in data["items"]:
                if e["id"] <= latest_id:
                    break

                print(f'new entry ({e["id"]}) named "{e["title"]}" from brand "{e["brand_title"]}" for {e["price"]} {e["currency"]} at {e["url"]}')
            else:
                time.sleep(0.2)
                p += 1
                data = seekArticle(**REQ_PARAMS, page=p, search_session_id=data["search_tracking_params"]["search_session_id"])
                continue

            break

        #print("-" * 80)
        
    latest_id = max(latest_id, new_latest_id)
    # anti-spam
    time.sleep(2)



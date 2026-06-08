"""
Playwright Threads worker — 獨立 subprocess 執行，避免 greenlet 衝突。
從 stdin 讀 JSON 指令，結果輸出到 stdout JSON。
使用 browser_cookie3 讀取 Chrome 已登入的 Threads session。
"""
import sys, json, re, time, os, urllib.parse


def _load_cookies_file(cookies_path):
    """從 .threads_cookies.json 讀取 cookies，回傳 Playwright 格式 list"""
    import json as _json
    if not os.path.exists(cookies_path):
        return []
    try:
        cookie_dict = _json.load(open(cookies_path))
    except Exception:
        return []
    pw_cookies = []
    for name, value in cookie_dict.items():
        pw_cookies.append({
            "name": name,
            "value": str(value),
            "domain": ".threads.com",
            "path": "/",
            "secure": True,
            "sameSite": "None",
        })
    return pw_cookies


def run_check_cookies(cookies_path):
    """確認 cookies 檔案是否存在且有效"""
    cookies = _load_cookies_file(cookies_path)
    has_session = any(c["name"] in ("ds_user_id", "sessionid") for c in cookies)
    return {"ok": True, "has_session": has_session, "count": len(cookies)}


def run_search(keywords, cookies_path, max_accounts=25, **_):
    from playwright.sync_api import sync_playwright

    SKIP = {"tag", "explore", "login", "register", "about", "help", "privacy",
            "p", "www", "search", "threads", "meta", "instagram"}

    pw_cookies = _load_cookies_file(cookies_path)
    if not any(c["name"] in ("ds_user_id", "sessionid") for c in pw_cookies):
        return {"ok": False, "error": "未設定 Threads cookies，請先在工具內完成「連線 Threads」步驟"}

    found = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        try:
            ctx.add_cookies(pw_cookies)
        except Exception:
            pass
        page = ctx.new_page()

        try:
            for kw in keywords[:5]:
                url = f"https://www.threads.com/search?q={urllib.parse.quote(kw)}&serp_type=default"
                page.goto(url, timeout=25000)
                page.wait_for_timeout(3500)
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(1500)

                if "login" in page.url:
                    return {"ok": False, "error": "Chrome Threads session 已過期，請重新在 Chrome 登入 threads.com"}

                content = page.content()
                for m in re.finditer(r'href="/@([\w.]+)"', content):
                    u = m.group(1).lower()
                    if u not in SKIP and u not in found:
                        found[u] = {"handle": "@" + u, "profile_url": f"https://www.threads.com/@{u}"}
                for m in re.finditer(r'"username"\s*:\s*"([\w.]+)"', content):
                    u = m.group(1).lower()
                    if u not in SKIP and u not in found:
                        found[u] = {"handle": "@" + u, "profile_url": f"https://www.threads.com/@{u}"}
                if len(found) >= max_accounts:
                    break
                time.sleep(1)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            try:
                page.close()
                ctx.close()
                browser.close()
            except Exception:
                pass

    return {"ok": True, "results": list(found.values())[:max_accounts]}


def _parse_count_str(text):
    text = str(text).replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*萬", text)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.match(r"^(\d+)$", text)
    if m:
        return int(m.group(1))
    return None


def _parse_threads_posts(data, seen_ids):
    results = []

    def recurse(obj):
        if isinstance(obj, dict):
            pk = obj.get("pk") or obj.get("id")
            view_count = obj.get("view_count") or obj.get("play_count")
            like_count = obj.get("like_count") or obj.get("fb_like_count")
            if pk and str(pk) not in seen_ids and (view_count is not None or like_count is not None):
                seen_ids.add(str(pk))
                results.append({
                    "views": int(view_count) if view_count is not None else None,
                    "likes": int(like_count) if like_count is not None else None,
                    "replies": obj.get("direct_reply_count") or obj.get("reply_count"),
                })
            for v in obj.values():
                recurse(v)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)

    recurse(data)
    return results


def _parse_html_for_posts(content, num_posts=5):
    posts = []
    for pat in [r'"view_count"\s*:\s*(\d+)', r'"play_count"\s*:\s*(\d+)']:
        counts = list(dict.fromkeys(int(m) for m in re.findall(pat, content) if int(m) > 0))
        if counts:
            for i, c in enumerate(counts[:num_posts]):
                posts.append({"index": i + 1, "views": c, "likes": None})
            break
    return posts


def run_profile_posts(username, cookies_path, num_posts=5, **_):
    from playwright.sync_api import sync_playwright

    pw_cookies = _load_cookies_file(cookies_path)
    if not any(c["name"] in ("ds_user_id", "sessionid") for c in pw_cookies):
        return {"ok": False, "error": "請先連線 Threads"}

    captured_bodies = []

    def handle_route(route, request):
        """用 route.fetch() 確保能拿到完整 response body"""
        try:
            response = route.fetch()
            ct = response.headers.get("content-type", "")
            if "json" in ct:
                body = response.text()
                if 50 < len(body) < 2_000_000 and ("view_count" in body or "like_count" in body):
                    captured_bodies.append(body)
            route.fulfill(response=response)
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass

    posts = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        try:
            ctx.add_cookies(pw_cookies)
        except Exception:
            pass
        page = ctx.new_page()

        # route() 比 on("response") 可靠：route.fetch() 保證 body 已接收完整
        for pattern in ["**threads.com/api/**", "**threads.net/api/**", "**i.instagram.com/api/**"]:
            page.route(pattern, handle_route)

        try:
            page.goto(f"https://www.threads.com/@{username}", timeout=30000)
            page.wait_for_timeout(5000)

            if "login" in page.url:
                return {"ok": False, "error": "Threads session 已過期，請重新連線"}

            seen_ids = set()
            for body in captured_bodies:
                try:
                    parsed = json.loads(body)
                    extracted = _parse_threads_posts(parsed, seen_ids)
                    posts.extend(extracted)
                    if len(posts) >= num_posts:
                        break
                except Exception:
                    pass

            if not posts:
                content = page.content()
                posts = _parse_html_for_posts(content, num_posts)

        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            try:
                page.close()
                ctx.close()
                browser.close()
            except Exception:
                pass

    for i, p in enumerate(posts[:num_posts]):
        p["index"] = i + 1

    return {"ok": True, "posts": posts[:num_posts]}


if __name__ == "__main__":
    cmd = json.loads(sys.stdin.read())
    action = cmd.get("action")
    cookies_path = cmd.get("cookies_path", os.path.join(os.path.dirname(__file__), ".threads_cookies.json"))

    if action == "check_cookies":
        result = run_check_cookies(cookies_path)
    elif action == "search":
        result = run_search(cmd["keywords"], cookies_path=cookies_path, max_accounts=cmd.get("max_accounts", 25))
    elif action == "profile_posts":
        result = run_profile_posts(cmd["username"], cookies_path=cookies_path, num_posts=cmd.get("num_posts", 5))
    else:
        result = {"ok": False, "error": f"Unknown action: {action}"}

    print(json.dumps(result, ensure_ascii=False))

import os
import sys
import json
import time
import re
import random
import webbrowser
import threading
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, send_file

# =========================================================================
# 🌟 【终极杀手锏】彻底抛弃常规 webdriver.Chrome，直接显式导入底层真实类！
# 这样可以 100% 免疫 PyInstaller 打包时漏掉 Selenium 动态模块的致命 BUG
# =========================================================================
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
app = Flask(__name__)

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
LOG_FILE = os.path.join(BASE_DIR, "quiz_log.txt")
RUN_LOG_FILE = os.path.join(BASE_DIR, "run.log")

active_driver = None
stop_flag = False
worker_thread = None
cloudflare_url = "正在检测并连接外网穿透..."

class ForceStopException(Exception): pass

def start_cloudflare_tunnel():
    global cloudflare_url
    cf_path = os.path.join(BASE_DIR, 'cloudflared.exe')
    if not os.path.exists(cf_path):
        cloudflare_url = "未找到 cloudflared.exe，仅支持本地访问"
        return
    try:
        kwargs = {}
        if sys.platform == "win32": kwargs['creationflags'] = 0x08000000 
        proc = subprocess.Popen([cf_path, "tunnel", "--url", "http://127.0.0.1:5000"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)
        def read_output():
            global cloudflare_url
            for line in proc.stdout:
                match = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', line)
                if match:
                    cloudflare_url = match.group(1)
                    print(f"\n🌍 成功获取外网穿透地址: {cloudflare_url}\n")
        threading.Thread(target=read_output, daemon=True).start()
    except Exception as e:
        cloudflare_url = f"穿透启动失败: {str(e)}"

def load_config():
    if not os.path.exists(CONFIG_FILE): return {"name": "", "settings": {}}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

def check_time_limits(end_time_limit):
    global stop_flag
    if stop_flag: raise ForceStopException("🛑 任务已被用户强制停止！")
    current_time = datetime.now()
    hard_stop_limit = datetime(current_time.year, current_time.month, current_time.day, 23, 59, 59)
    if current_time >= hard_stop_limit: raise ForceStopException("🛑 触发绝对规则：晚上12点已到，强行终止！")
    if end_time_limit and current_time >= end_time_limit: raise ForceStopException("🛑 触发设定的强制结束时间，任务终止！")

def smart_sleep(seconds, end_time_limit):
    end_time = time.time() + seconds
    while time.time() < end_time:
        check_time_limits(end_time_limit)
        time.sleep(0.05)

def generate_random_delays(total_time, count=10, min_time=0.5):
    if total_time < count * min_time: return [total_time / count] * count
    remaining = total_time - count * min_time
    splits = [0.0] + sorted([random.uniform(0, remaining) for _ in range(count - 1)]) + [remaining]
    return [(splits[i+1] - splits[i]) + min_time for i in range(count)]

def human_bezier_click(driver, element, end_time_limit):
    try:
        tx, ty = random.randint(-5, 5), random.randint(-2, 2)
        sx, sy = random.randint(-150, 150), random.randint(-100, -50)
        c1x, c1y = sx + random.randint(-50, 50), sy + random.randint(-20, 50)
        c2x, c2y = tx + random.randint(-50, 50), ty + random.randint(-50, 20)
        steps = random.randint(15, 25)
        path = []
        for i in range(steps):
            t = i / (steps - 1)
            t = 1 - (1 - t) ** 3
            x = (1-t)**3 * sx + 3*(1-t)**2 * t * c1x + 3*(1-t)* t**2 * c2x + t**3 * tx
            y = (1-t)**3 * sy + 3*(1-t)**2 * t * c1y + 3*(1-t)* t**2 * c2y + t**3 * ty
            path.append((int(x), int(y)))
        action = ActionChains(driver)
        action.move_to_element_with_offset(element, path[0][0], path[0][1])
        px, py = path[0]
        for p in path[1:]:
            action.move_by_offset(p[0] - px, p[1] - py)
            action.pause(random.uniform(0.01, 0.03)) 
            px, py = p
        action.pause(random.uniform(0.1, 0.3)).click().perform()
    except Exception:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            ActionChains(driver).move_to_element(element).pause(random.uniform(0.2, 0.5)).click().perform()
        except:
            driver.execute_script("arguments[0].click();", element)

def human_type_with_time(element, text, total_time, end_time_limit):
    smart_sleep(total_time * 0.3, end_time_limit)  
    type_time = total_time * 0.7   
    if len(text) > 0:
        delay = type_time / len(text)
        for char in text:
            element.send_keys(char)
            smart_sleep(delay, end_time_limit)
    else: smart_sleep(type_time, end_time_limit)

def human_click_with_time(driver, element, total_time, end_time_limit):
    smart_sleep(total_time * 0.7, end_time_limit)
    human_bezier_click(driver, element, end_time_limit)

def normalize_text(text): return "".join(str(text).split())

def log_run(message):
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
    with open(RUN_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

def create_chrome_driver(phone_proxy=""):
    options = ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    if phone_proxy:
        options.add_argument(f'--proxy-server=socks5://{phone_proxy}')
    driver = ChromeDriver(options=options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })
    driver.maximize_window()
    return driver

def parse_math_answer(text):
    if not text:
        return None
    cleaned = str(text).strip()
    for src, dst in [('×', '*'), ('÷', '/'), ('x', '*'), ('X', '*'), ('＋', '+'), ('－', '-')]:
        cleaned = cleaned.replace(src, dst)
    cleaned = re.sub(r'[^0-9+\-*/]', '', cleaned)
    match = re.search(r'(\d+)\s*([+\-*/])\s*(\d+)', cleaned)
    if not match:
        digits = re.findall(r'\d+', str(text))
        if len(digits) >= 2:
            return int(digits[0]) + int(digits[1])
        return None
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    if op == '+': return a + b
    if op == '-': return a - b
    if op == '*': return a * b
    if op == '/': return a // b if b else None
    return None

def get_captcha_ocr():
    try:
        import ddddocr
        return ddddocr.DdddOcr(show_ad=False)
    except ImportError:
        return None

def solve_math_captcha(driver, wait, end_time_limit, max_attempts=10):
    ocr = get_captcha_ocr()
    if ocr is None:
        log_run("❌ 未安装 ddddocr，请运行: pip install ddddocr")
        return False

    try:
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.ID, "cq-cap-overlay"))
        )
    except TimeoutException:
        return True

    for attempt in range(max_attempts):
        check_time_limits(end_time_limit)
        try:
            img_el = wait.until(EC.presence_of_element_located((By.ID, "cq-cap-img")))
            smart_sleep(0.6, end_time_limit)
            text = ocr.classification(img_el.screenshot_as_png)
            answer = parse_math_answer(text)
            log_run(f"🔢 验证码 OCR: {text!r} → {answer}")

            if answer is None:
                driver.find_element(By.ID, "cq-cap-refresh").click()
                smart_sleep(0.8, end_time_limit)
                continue

            cap_input = driver.find_element(By.ID, "cq-cap-input")
            cap_input.clear()
            cap_input.send_keys(str(answer))
            smart_sleep(0.3, end_time_limit)
            human_bezier_click(driver, driver.find_element(By.ID, "cq-cap-btn"), end_time_limit)

            WebDriverWait(driver, 8).until(
                EC.invisibility_of_element_located((By.ID, "cq-cap-overlay"))
            )
            return True
        except TimeoutException:
            msg_el = driver.find_elements(By.ID, "cq-cap-msg")
            err = msg_el[0].text.strip() if msg_el and msg_el[0].text.strip() else "验证失败"
            log_run(f"⚠️ 验证码第 {attempt + 1} 次失败: {err}")
            try:
                driver.find_element(By.ID, "cq-cap-refresh").click()
                smart_sleep(0.8, end_time_limit)
            except Exception:
                pass
        except Exception as e:
            log_run(f"⚠️ 验证码异常: {e}")
            smart_sleep(1, end_time_limit)

    return False

def select_class_option(driver, wait, class_name, end_time_limit):
    def class_ready(d):
        sel = d.find_element(By.ID, "cq-class-name")
        return len(Select(sel).options) > 1

    wait.until(class_ready)
    class_select = Select(driver.find_element(By.ID, "cq-class-name"))
    for option in class_select.options:
        if normalize_text(option.text) == normalize_text(class_name) or class_name in option.text:
            class_select.select_by_visible_text(option.text)
            return
    if len(class_select.options) > 1:
        class_select.select_by_index(1)

def run_one_quiz(quiz_bank, c, end_time_limit, student_name):
    global active_driver
    school_id = c.get("SCHOOL_ID", "3719").strip()
    class_name = c.get("CLASS_NAME", "高二 Form 5").strip()
    group_name = c.get("GROUP_NAME", "甲").strip()
    form_fill_time = float(c.get("FORM_FILL_TIME", 10))
    total_quiz_time = float(c.get("TOTAL_QUIZ_TIME", 45))
    quiz_score_range = (int(c.get("QUIZ_SCORE_MIN", 80)), int(c.get("QUIZ_SCORE_MAX", 100)))
    phone_proxy = c.get("PHONE_PROXY", "").strip()

    driver = create_chrome_driver(phone_proxy)
    active_driver = driver
    wait = WebDriverWait(driver, 15)
    score_int = 0

    try:
        check_time_limits(end_time_limit)
        driver.get("https://antidrugteens.com/quiz/")
        fill_delays = generate_random_delays(form_fill_time, count=6, min_time=0.5)

        human_click_with_time(driver, wait.until(EC.element_to_be_clickable((By.ID, "cq-gate-start"))), fill_delays[0], end_time_limit)
        human_type_with_time(wait.until(EC.visibility_of_element_located((By.ID, "cq-school-id"))), school_id, fill_delays[1], end_time_limit)
        human_click_with_time(driver, driver.find_element(By.ID, "cq-verify-btn"), fill_delays[2], end_time_limit)
        wait.until(lambda d: d.find_element(By.ID, "cq-school-id").get_attribute("disabled"))
        wait.until(EC.visibility_of_element_located((By.ID, "cq-student-name")))
        select_class_option(driver, wait, class_name, end_time_limit)
        human_type_with_time(driver.find_element(By.ID, "cq-student-name"), student_name, fill_delays[3], end_time_limit)
        human_type_with_time(driver.find_element(By.ID, "cq-group"), group_name, fill_delays[4], end_time_limit)
        human_click_with_time(driver, driver.find_element(By.ID, "cq-start-btn"), fill_delays[5], end_time_limit)

        wait.until(lambda d: "quiz-play" in d.current_url)
        smart_sleep(1, end_time_limit)

        if not solve_math_captcha(driver, wait, end_time_limit):
            log_run("❌ 数字验证码未能通过，跳过本轮")
            return 0

        wait.until(EC.visibility_of_element_located((By.ID, "cq-quiz-wrap")))
        target_round_score = random.choice(range(quiz_score_range[0], quiz_score_range[1] + 10, 10))
        wrong_count = (100 - target_round_score) // 10
        wrong_indices = set(random.sample(range(10), wrong_count))
        delays = generate_random_delays(total_quiz_time, count=10)

        for i in range(10):
            smart_sleep(delays[i], end_time_limit)
            question_area = wait.until(EC.presence_of_element_located((By.ID, "cq-question-area")))
            live_q_norm = normalize_text(question_area.text)
            correct_answer = next((a for q, a in quiz_bank.items() if normalize_text(q) in live_q_norm), None)
            
            if correct_answer:
                ans_norm = normalize_text(correct_answer)
                is_wrong_target = i in wrong_indices
                clickable = question_area.find_elements(By.CSS_SELECTOR, "label, button, .cq-option, [role='button']")
                if not clickable:
                    clickable = question_area.find_elements(By.XPATH, ".//*")
                correct_elem = next((opt for opt in reversed(clickable) if opt.text and ans_norm in normalize_text(opt.text)), None)

                if correct_elem:
                    if not is_wrong_target:
                        human_bezier_click(driver, correct_elem, end_time_limit)
                    else:
                        cy, cx = correct_elem.location['y'], correct_elem.location['x']
                        for opt in reversed(clickable):
                            opt_text = normalize_text(opt.text)
                            if opt_text and 1 < len(opt_text) < 100 and ans_norm not in opt_text:
                                if "第" not in opt_text and "共" not in opt_text and "题" not in opt_text and "已答" not in opt_text:
                                    if abs(opt.location['y'] - cy) > 30 or abs(opt.location['x'] - cx) > 30:
                                        human_bezier_click(driver, opt, end_time_limit)
                                        break
                                        
            if i < 9: human_bezier_click(driver, driver.find_element(By.ID, "cq-btn-next"), end_time_limit)
            else: human_bezier_click(driver, driver.find_element(By.ID, "cq-btn-submit"), end_time_limit)

        try:
            WebDriverWait(driver, 1.5).until(EC.alert_is_present()).accept()
        except Exception:
            pass

        try:
            WebDriverWait(driver, 15).until(lambda d: "quiz-result" in d.current_url or "quiz-play" in d.current_url)
        except TimeoutException:
            pass

        def poll_score_from_page(d):
            try:
                txt = d.find_element(By.TAG_NAME, "body").text
                for pt in [r'(?:得分|分数|成绩|最终得分|总分)[:：]\s*(\d+)', r'(\d+)\s*分', r'Score[:：]\s*(\d+)', r'答對\s*(\d+)\s*題']:
                    m = re.search(pt, txt)
                    if m: return str(int(m.group(1)) * 10) if "答對" in pt else m.group(1)
                for e in d.find_elements(By.XPATH, "//*[contains(text(), '分') or contains(@class, 'score')]"):
                    digits = "".join(filter(str.isdigit, e.text))
                    if digits and 0 <= int(digits) <= 100: return digits
            except: pass
            return False

        try: final_score_str = WebDriverWait(driver, 8, poll_frequency=0.1).until(poll_score_from_page)
        except: final_score_str = "0"

        log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{log_time}] {student_name} - 提交分数: {final_score_str}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
        
        try: score_int = int(final_score_str)
        except ValueError: score_int = 0  

    except ForceStopException as fse:
        try: driver.quit()
        except: pass
        raise fse
    except Exception as e:
        log_run(f"❌ 答题异常: {e}")
    finally:
        try: driver.quit()
        except: pass
        active_driver = None
    return score_int

def wait_for_start_time(start_time_str, end_time_limit):
    if not start_time_str.strip(): return
    try: target_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError: return
    if target_time <= datetime.now(): return
    while True:
        now_time = datetime.now()
        if now_time >= target_time: break
        check_time_limits(end_time_limit)
        time.sleep(1)

def run_engine_thread():
    global active_driver, stop_flag
    
    try:
        with open(os.path.join(BASE_DIR, 'quiz_bank.json'), 'r', encoding='utf-8') as f: quiz_bank = json.load(f)
    except:
        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f: f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 启动失败：未找到 quiz_bank.json\n")
        return

    config_data = load_config()
    student_name = config_data.get('name')
    c = config_data.get('settings', {})
    
    start_time_str, end_time_str = c.get("START_TIME", ""), c.get("END_TIME", "")
    end_time_limit = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S") if end_time_str else None

    actual_target_score = random.choice(range(int(c.get("TARGET_SCORE_MIN", 400)), int(c.get("TARGET_SCORE_MAX", 600)) + 10, 10))
    rest_score_min, rest_score_max = int(c.get("REST_AFTER_SCORE_MIN", 150)), int(c.get("REST_AFTER_SCORE_MAX", 250))
    rest_duration_min, rest_duration_max = int(c.get("REST_DURATION_MIN", 3)), int(c.get("REST_DURATION_MAX", 5))
    pause_min, pause_max = float(c.get("PAUSE_MIN", 5)), float(c.get("PAUSE_MAX", 45))

    accumulated_score = 0  
    score_since_rest = 0   
    current_rest_threshold = random.choice(range(rest_score_min, rest_score_max + 10, 10))

    try:
        wait_for_start_time(start_time_str, end_time_limit)
        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f: f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🟢 引擎就绪！目标: {actual_target_score} 分\n")

        while accumulated_score < actual_target_score:
            check_time_limits(end_time_limit)
            score_obtained = run_one_quiz(quiz_bank, c, end_time_limit, student_name)
            accumulated_score += score_obtained
            score_since_rest += score_obtained
            
            if accumulated_score >= actual_target_score:
                with open(RUN_LOG_FILE, "a", encoding="utf-8") as f: f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🎉 圆满完成！(目标:{actual_target_score} 累计:{accumulated_score})\n")
                break
                
            if score_since_rest >= current_rest_threshold:
                rest_minutes = random.randint(rest_duration_min, rest_duration_max)
                with open(RUN_LOG_FILE, "a", encoding="utf-8") as f: f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ☕ 已获 {score_since_rest} 分，大长休 {rest_minutes} 分钟...\n")
                smart_sleep(rest_minutes * 60, end_time_limit)
                score_since_rest = 0
                current_rest_threshold = random.choice(range(rest_score_min, rest_score_max + 10, 10))
            else:
                smart_sleep(random.randint(int(pause_min), int(pause_max)), end_time_limit)
            
    except ForceStopException as e:
        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f: f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {str(e)}\n")

@app.route('/')
def index(): return send_file(resource_path('index.html'))

@app.route('/api/config', methods=['GET'])
def get_config(): return jsonify(load_config())

@app.route('/api/setup', methods=['POST'])
def setup_server():
    name = request.json.get('name', '').strip()
    if not name: return jsonify({"error": "姓名不能为空"}), 400
    config = load_config()
    config['name'] = name
    config['settings'] = {
        "TOTAL_QUIZ_TIME": 45, "FORM_FILL_TIME": 15, 
        "TARGET_SCORE_MIN": 400, "TARGET_SCORE_MAX": 600,
        "QUIZ_SCORE_MIN": 80, "QUIZ_SCORE_MAX": 100, 
        "PAUSE_MIN": 5, "PAUSE_MAX": 45,
        "REST_AFTER_SCORE_MIN": 150, "REST_AFTER_SCORE_MAX": 250, 
        "REST_DURATION_MIN": 3, "REST_DURATION_MAX": 5,
        "START_TIME": "", "END_TIME": "", "PHONE_PROXY": "",
        "SCHOOL_ID": "3719", "CLASS_NAME": "高二 Form 5", "GROUP_NAME": "甲"
    }
    save_config(config)
    return jsonify({"success": True})

@app.route('/api/settings', methods=['POST'])
def save_settings():
    config = load_config()
    if not config.get('name'): return jsonify({"error": "未初始化"}), 400
    config['settings'] = request.json
    save_config(config)
    return jsonify({"success": True})

@app.route('/api/status', methods=['GET'])
def get_status():
    global worker_thread
    is_running = worker_thread is not None and worker_thread.is_alive()
    return jsonify({"running": is_running})

@app.route('/api/run', methods=['POST'])
def run_script():
    global worker_thread, stop_flag, active_driver
    config = load_config()
    if not config.get('name'): return jsonify({"error": "未初始化"}), 400
    if worker_thread is not None and worker_thread.is_alive(): return jsonify({"error": "已经在运转中！"}), 400

    stop_flag, active_driver = False, None
    try: open(RUN_LOG_FILE, 'w', encoding='utf-8').close()
    except: pass
    
    worker_thread = threading.Thread(target=run_engine_thread, daemon=True)
    worker_thread.start()
    return jsonify({"success": True})

@app.route('/api/stop', methods=['POST'])
def stop_script():
    global stop_flag, active_driver
    stop_flag = True
    if active_driver:
        try: active_driver.quit()
        except: pass
        active_driver = None
    return jsonify({"success": True, "message": "已强制停止任务"})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    if os.path.exists(RUN_LOG_FILE):
        with open(RUN_LOG_FILE, 'r', encoding='utf-8') as f: return jsonify({"log": f.read()})
    return jsonify({"log": "暂无日志..."})

@app.route('/api/tunnel', methods=['GET'])
def get_tunnel():
    return jsonify({"url": cloudflare_url})

if __name__ == '__main__':
    start_cloudflare_tunnel()
    try: webbrowser.open("http://127.0.0.1:5000")
    except: pass
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
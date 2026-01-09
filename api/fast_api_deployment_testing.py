import subprocess
import time, requests

#service_url = "https://risk-lab-api-lkqbrgzs6a-uc.a.run.app"
global service_url
service_url = "https://risk-lab-api-lkqbrgzs6a-uc.a.run.app"

def is_deployed():
    try:
        response = subprocess.run(["curl", f"{service_url}/health"], capture_output=True, text=True)
        return '"ok":true' in response.stdout
    except Exception:
        return False

def deploy():
    if not is_deployed():
        print("Attempting to deploy the service...")
        try:
            response = subprocess.run([
                "gcloud", "run", "deploy", "risk-lab-api",
                "--image", "gcr.io/risk-assesser/risk-lab-api",
                "--region", "us-central1",
                "--allow-unauthenticated",
                "--project", "risk-assesser",
            ], check=True, capture_output=True, text=True)
            if "Service URL" in response.stdout:
                print("Deployment successful.")
                service_url_line = [line for line in response.stdout.splitlines() if "Service URL" in line][0]
                global service_url
                service_url = service_url_line.split(": ")[1]
                print(f"Service URL: {service_url}")
            else:
                print("No service URL found in deployment output.")
        except Exception as e:
            print(f"Deployment failed: {e}")
    else:
        print(f"Service is already deployed at {service_url}")

def check_deployment_status():
    if is_deployed():
        try:
            response = subprocess.run(
                ["curl", "-X", "POST", f"{service_url}/runs", "-H", "Content-Type: application/json", 
                "-d", '{"n_sims":50000,"capital":1000000,"config":{"note":"cloud"}}'], capture_output=True, text=True)
            if "\"status\":\"queued\"" in response.stdout:
                print("Deployment is healthy and responding correctly.")
                return True
            else:
                print("Deployment is active but not responding as expected.", response.stdout)
                return False
        except Exception as e:
            print("Cannot check deployment status:", e)
            return False
    else:
        print("Service is not deployed.")
        check = input("Would you like to deploy it now? (y/n): ")
        if check.lower() == 'y':
            deploy()

def get_run_id():
    try:
        response = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{service_url}/runs", "-H", "Content-Type: application/json", "-d", '{"n_sims":50000,"capital":1000000,"config":{"note":"day2"}}'], 
            capture_output=True, text=True)
        lines = response.stdout.splitlines()
        for line in lines:
            if '"run_id":"' in line:
                start = line.index('"run_id":"') + len('"run_id":"')
                end = line.index('"', start)
                return line[start:end]
        return None
    except Exception as e:
        print("Error fetching run ID:", e)
        return None

API_URL = "https://risk-lab-api-lkqbrgzs6a-uc.a.run.app"
def poll_until_done(run_id, timeout=300, interval=2):
    url = f"{API_URL}/runs/{run_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        status = r.json().get("status")
        print("status =", status)
        if status and status != "queued":
            return r.json()
        time.sleep(interval)
    raise TimeoutError("Timed out waiting for run to finish")

def check_run_completion(run_id):
    url = f"{API_URL}/runs/{run_id}"
    try:
        response = subprocess.run(["curl", url, "|", "python", "-m", "json.tool"], check=True, 
                                  capture_output=True, text=True)
        print("Run details:", response.stdout)
    except Exception as e:
        check_run_id = input("Would you like to check jobs with that run ID? (y/n): ")
        if check_run_id.lower() == 'y':
            try:
                response = subprocess.run(["gcloud", "run", "jobs", "executions", "list", 
                                           "--filter", f"metadata.labels.run_id={run_id}"], capture_output=True, text=True)
                print("Job executions:", response.stdout)
            except Exception as ex:
                print("Could not get job executions:", ex)
if __name__ == "__main__":
    if(check_deployment_status()):
        run_id = get_run_id()
        print(f"Run ID: {run_id}")
        check_poll = input("Would you like to poll for completion? (y/n): ")
        if check_poll.lower() == 'y' and run_id:
            final = poll_until_done(run_id, timeout=600)
            check_completion = input("Would you like tyo check run completion details? (y/n): ")
            if check_completion.lower() == 'y':
                check_run_completion(run_id)


'''
Create jobs:
gcloud run jobs create risk-lab-worker \
  --image gcr.io/risk-assesser/risk-lab:latest \
  --service-account risk-lab-worker@risk-assesser.iam.gserviceaccount.com \
  --command python \
  --args="-m,app.worker" \
  --max-retries 1 \
  --task-timeout 10m

  Execute jobs: gcloud run execute risk-lab-worker
'''
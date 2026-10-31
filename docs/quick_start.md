# Quick Start Guide

First, you need to register a YouCam API account for free at [https://yce.makeupar.com/ai-api](https://yce.makeupar.com/ai-api). You can then purchase or subscribe to get your units to use the service. You can see your subscription plan, pay as you go units, and your usage record at [https://yce.makeupar.com/api-console/en/api-keys/](https://yce.makeupar.com/api-console/en/api-keys/). You can go to the API Key tab under your account page to generate and maintain your API keys to start using the YouCam API.

### Workflow Steps:

#### 1. Authentication

- Include your API key in the request header using **Bearer Token**:

```
Authorization: Bearer YOUR_API_KEY
```


You can find your API Key at [https://yce.makeupar.com/api-console/en/api-keys/](https://yce.makeupar.com/api-console/en/api-keys/).

#### 2. Upload a File or Preparing a Public Image URL.

- Invoke the **File API**
- Get an ulpoad URL `requests.url` and a corresponding `file_id` from the File API response.
- Use the `requests.url` from the File API response to upload the image


#### 3. Initiate AI Task and Obtain Task ID:

- Send the uploaded image along with the AI task configuration via an HTTP POST request to `/s2s/v2.0/task/skin-analysis`. Use AI Skin Analysis task here for example.
- Await a unique task ID in the response, which identifies this interaction.


#### 4. Poll Task Status (Continuous Check):

- Use the obtained `task_id` to periodically poll the task status using an HTTP GET request (e.g., `GET /skin-analysis/${task_id}`). Use AI Skin Analysis task here for example.
- Continuously monitor for:
  - `Task_status = "success"` (process completed).
  - `Task_status = "error"` (resolve or retry if applicable).
- Update the workflow accordingly once the status transitions to success.


#### 5. Retrieve Result

- A successful response includes a download URL for the result image.
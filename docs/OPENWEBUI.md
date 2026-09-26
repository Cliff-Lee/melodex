# OpenWebUI

In Melodex open **Ask Melodex → Connect LLM** and choose **openwebui**.

Typical endpoint:

```text
http://localhost:3000/api/chat/completions
```

Enter a model name that OpenWebUI exposes and an API key if your OpenWebUI configuration requires one.

If OpenWebUI is running in Docker but Melodex runs directly on the same computer, `localhost:3000` normally works when the container publishes port 3000. If not, use the host/port you configured for OpenWebUI.

Melodex sends compact listening context only when you submit a prompt.

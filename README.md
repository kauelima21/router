# Router

Pacote simples para manipulacao de rotas e eventos do API Gateway (v1 e v2) com Lambda functions.

Zero dependencias externas — utiliza apenas a stdlib do Python.

## Instalacao

```bash
uv add git+https://github.com/kauelima21/router.git
```

## Uso basico

```python
from router import Router

router = Router()

def list_users(req, res):
    return res.json({"users": []})

def create_user(req, res):
    name = req.body.get("name")
    return res.status(201).json({"name": name})

router.get("/users", list_users)
router.post("/users", create_user)

# handler da Lambda
def handler(event, context):
    return router.dispatch(event)
```

## API Gateway v1 e v2

O router detecta automaticamente o formato do evento (REST API v1 ou HTTP API v2):

```python
# Auto-detect (padrao)
router = Router()

# Forcar versao especifica
router = Router(api_version="v1")   # REST API
router = Router(api_version="v2")   # HTTP API
```

A deteccao usa a presenca da chave `routeKey` (v2) ou `httpMethod` (v1) no evento.

## Catch-all (`/{proxy+}`) integration

O router aceita integracoes catch-all do API Gateway HTTP API sem configuracao extra. Quando o `routeKey` vem generico (ex.: `ANY /{proxy+}`), o dispatch faz fallback automatico para um match por regex sobre o `rawPath`, extraindo path parameters nomeados.

```yaml
# serverless.yml — uma unica integracao cobre todas as rotas
functions:
  api:
    handler: index.handler
    events:
      - httpApi:
          method: "*"
          path: /{proxy+}
```

```python
router.get("/api/v1/users/{id}", show_user)
# Request para /api/v1/users/42 com routeKey="ANY /{proxy+}"
# -> handler chamado, req.params["id"] == "42"
```

Regras:

- O match exato `(method, path)` continua sendo tentado primeiro (fast path).
- O fallback por regex respeita o metodo HTTP — `POST /users` nao responde a `GET /users`.
- `{param}` casa um unico segmento de URL (nao atravessa `/`).
- Multiplos path parameters sao suportados (`/courses/{course_id}/modules/{module_id}`).
- Middlewares, grupos e resolucao de handler por string continuam funcionando identicamente.

## Agrupamento de rotas

```python
router.group("auth")
router.post("/sign-in", sign_in_handler)
router.post("/sign-up", sign_up_handler)
# Registra: POST /auth/sign-in, POST /auth/sign-up

router.group("users")
router.get("/list", list_handler)
# Registra: GET /users/list

router.group(None)  # remove o prefixo
router.get("/health", health_handler)
# Registra: GET /health
```

## Request

O objeto `Request` normaliza os campos do evento independente da versao:

| Atributo             | Descricao                                         |
|----------------------|----------------------------------------------------|
| `method`             | Metodo HTTP (`GET`, `POST`, etc.)                  |
| `path`               | Rota registrada (`/users/{id}`)                    |
| `raw_path`           | Path real da requisicao (`/users/42`)              |
| `query`              | Query string como `dict`                           |
| `params`             | Path parameters como `dict`                        |
| `headers`            | Headers da requisicao                              |
| `body`               | Body parseado como `dict` (JSON)                   |
| `raw_body`           | Body original como `str`                           |
| `authenticated_user` | Claims do JWT (Cognito/authorizer)                 |
| `request_context`    | `requestContext` original do evento                |

## Response

Fluent interface para construir a resposta:

```python
# JSON
return res.json({"id": 1, "name": "Kaue"})

# Texto
return res.send("OK")

# Status code + JSON
return res.status(201).json({"created": True})

# Headers customizados
return res.set("X-Request-Id", "abc-123").json({"ok": True})

# Cookies
return res.cookie("session=abc; HttpOnly; Secure").json({"ok": True})
```

## Metodos HTTP suportados

```python
router.get(path, handler)
router.post(path, handler)
router.put(path, handler)
router.delete(path, handler)
router.patch(path, handler)
router.options(path, handler)
router.head(path, handler)
```

## Middleware

Todos os metodos HTTP aceitam um parametro opcional `middleware`. O middleware e um callable que recebe `(request, response, next_fn)` e decide se a requisicao segue para o handler ou e interrompida.

```python
def auth_middleware(req, res, next_fn):
    token = req.headers.get("Authorization")
    if not token:
        return res.status(401).json({"error": "Token ausente"})
    return next_fn(req, res)

router.get("/users", list_users, middleware=auth_middleware)
router.post("/users", create_user, middleware=auth_middleware)

# Rotas sem middleware continuam funcionando normalmente
router.get("/health", health_handler)
```

O `next_fn` repassa a execucao para o handler. Se o middleware nao chamar `next_fn`, a requisicao e interrompida e a resposta retornada diretamente.

Caso uma excecao ocorra dentro do middleware ou do handler, o router ainda retorna `500` como fallback.

## Tratamento de erros

O router captura excecoes nao tratadas no handler e retorna `500` com corpo JSON:

```json
{"error": "Internal Server Error"}
```

Por padrao, o router loga warnings (404) e errors (500) via `logging`. Para desabilitar:

```python
router = Router(silent=True)
```

## Testes

```bash
uv run pytest
```

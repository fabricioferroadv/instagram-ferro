# Publicador do Instagram — Ferro Advocacia

Publica no `@fabricio.ferro.adv`, no horário marcado, os carrosséis que você
aprovou — **com o notebook desligado**. Roda de graça no GitHub Actions e
publica pela **API oficial da Meta**, sem nenhum intermediário (sem Windsor.ai,
Higgsfield, Zapier etc.).

```
Você aprova no chat  →  python fila.py agendar ... --enviar  →  GitHub (a cada 15 min)  →  Instagram
```

---

## Uso do dia a dia

Dentro desta pasta (`Instagram - Carrosseis\publicador-github`):

| Para… | Comando |
|---|---|
| Agendar um post aprovado | `python fila.py agendar <pasta> --quando "05/11/2026 19:00" --enviar` |
| Ver a fila, os erros e os publicados | `python fila.py listar` |
| Mudar o horário (ou recolocar um com erro) | `python fila.py reagendar <id> --quando "06/11/2026 12:00" --enviar` |
| Cancelar | `python fila.py cancelar <id> --enviar` |

`<pasta>` é o nome da subpasta em `PRONTOS PARA PUBLICAR` (com `01.jpg, 02.jpg…`
e `legenda.txt`, como hoje). Ou só me peça no chat: "agenda o carrossel X para
quinta às 19h".

**Horário:** o GitHub confere a fila a cada 15 minutos e às vezes atrasa um
pouco. Conte com o post saindo **até ~20 min depois** do horário marcado.

### O que acontece sozinho

| Situação | O que o sistema faz |
|---|---|
| Chegou o horário | Publica e move para `publicados/` com o link do post |
| Legenda com termo proibido pelo Provimento 205/2021 (ex.: "chama no direct", "consulta gratuita", "resultado garantido") | **Barra** já ao agendar. Se o uso for só informativo, libere de propósito com `--liberar "termo"` |
| Data no passado | Recusa ao agendar |
| O horário passou há mais de 3 h (ex.: GitHub fora do ar) | **Não publica fora de hora**: move para `erros/` e avisa |
| Meta recusou | Move para `erros/` com o motivo e avisa |
| A execução caiu no meio do envio | Move para `erros/` com "CONFIRA no Instagram" — nunca reenvia sozinho |
| Toda segunda | Confere o token e o prazo de acesso da Meta. Avisa 21 dias antes de vencer |

**Avisos:** quando algo dá errado, o GitHub manda **e-mail** para você
(execução "falhou"). Para conferir: aba **Actions** do repositório.

---

## Configuração (uma vez só)

### Passo 1 — Meta (você faz; exige seu login)

1. **Instagram profissional**: app do Instagram → Configurações → Tipo de conta →
   **Conta profissional** (Empresa ou Criador de conteúdo).
2. **Página do Facebook** da Ferro Advocacia, **vinculada** ao Instagram
   (Configurações da Página → Contas vinculadas → Instagram).
3. Em <https://developers.facebook.com> → **Meus apps** → **Criar app**:
   nome `Ferro Publicador`, caso de uso **"Gerenciar mensagens e conteúdo no
   Instagram"**, sem portfólio na criação.
4. No app → **Casos de uso → Personalizar**: conectar o portfólio
   **"Fabricio Ferro"** (exigido pela "API setup with Unified login") e criar a
   configuração pelo modelo (token de usuário do sistema, nunca expira).
5. **Funções do app → Testador do Instagram** → `fabricio.ferro.adv` e aceitar o
   convite no Instagram (Configurações → Permissões do site do app → Apps e
   sites → Convites do testador).

Feito em 03/11/2026 — app **Ferro Publicador**, ID `1654629516319767`.
Não precisa de App Review nem de verificação de empresa: o app só publica na sua
própria conta.

### Passo 2 — Token que não vence (usuário do sistema)

O botão "Adicionar conta" do painel de desenvolvedores falhou; este caminho
funcionou:

1. <https://business.facebook.com/settings> → portfólio **Fabricio Ferro**.
2. **Usuários → Usuários do sistema → Adicionar**: nome `publicador`, função
   **Funcionário** (Employee).
3. Atribuir ao `publicador`, com **controle total**:
   - **Contas → Páginas → Ferro Advocacia & Consultoria Jurídica → Atribuir pessoas**
   - **Contas → Perfis do Instagram → @fabricio.ferro.adv → Atribuir pessoas**
   - **Contas → Apps → Ferro Publicador → Atribuir pessoas**
4. No app (developers.facebook.com) → **Casos de uso → Personalizar → Permissões
   e recursos**: clicar em **Adicionar** em `instagram_basic` e
   `instagram_content_publish`. Sem isso a lista de permissões do token vem vazia.
5. **Usuários do sistema → publicador → Gerar token**: app Ferro Publicador,
   expiração **Nunca**, permissões `instagram_basic` + `instagram_content_publish`
   (+ `pages_read_engagement`, se liberada). A Meta mostra o token uma vez só.
6. **IG_ACCOUNT_ID** = `17841411125081467` (Contas → Perfis do Instagram).

**Não usar o "Conversions API System User"** — é dos pixels do site.

> ⚠️ O token dá poder de publicar no seu perfil. **Não cole no chat** nem em
> arquivo. Ele vai direto para o cofre do GitHub no passo 3.

### Passo 3 — GitHub

1. Crie uma conta gratuita em <https://github.com> (se ainda não tiver).
2. No terminal, dentro desta pasta:

```bash
gh auth login
```

```bash
gh repo create instagram-ferro --public --source . --push
```

```bash
gh secret set IG_ACCESS_TOKEN
```

(cola o token de Página quando pedir — não aparece na tela)

```bash
gh variable set IG_ACCOUNT_ID --body "17841411125081467"
```

Opcional, para a conferência semanal usar o token do app:

```bash
gh variable set FB_APP_ID --body "1654629516319767"
```

```bash
gh secret set FB_APP_SECRET
```

> O repositório é **público** porque a Meta precisa baixar as imagens por um
> link aberto. Por isso: **só entra aqui post já aprovado** — nunca documento
> de cliente. O token fica no cofre (secret), criptografado e invisível.

### Passo 4 — Testes (nesta ordem)

1. Aba **Actions** → **Verificar token da Meta** → **Run workflow** → deve ficar verde.
2. Agende um post de teste para daqui a 20 min:
   `python fila.py agendar teste-estilo-claro --quando "DD/MM/AAAA HH:MM" --enviar`
3. Abra no navegador o link de uma imagem
   (`https://raw.githubusercontent.com/SEU_USUARIO/instagram-ferro/main/midia/...`)
   — tem que abrir a imagem.
4. Espere o horário (ou **Actions → Publicar no Instagram → Run workflow**).
   O post aparece no perfil e o arquivo vai para `publicados/` com o link.
5. Apague o post de teste no Instagram, se quiser.

---

## Manutenção

- **Token:** o do usuário do sistema não expira. Se a conferência semanal acusar
  problema (token inválido ou prazo de acesso perto do fim), gere outro em
  **Usuários do sistema → publicador → Gerar token** (Passo 2, item 5) e rode
  `gh secret set IG_ACCESS_TOKEN` com o token novo.
- **Responder comentários (futuro):** gerar um token novo incluindo
  `instagram_manage_comments` e trocar o secret. Não está incluído hoje, de
  propósito (LGPD e Provimento 205/2021).
- **Agendamento desligado:** o GitHub desliga agendamentos de repositórios sem
  movimento por 60 dias. A conferência semanal grava `status/token.json`
  justamente para isso não acontecer. Se acontecer, ele avisa por e-mail; basta
  clicar em **Enable workflow** na aba Actions.
- **Limite da Meta:** 100 posts em 24 h. Não chegaremos perto.

## Arquivos

```
fila.py                         comandos que você usa (agendar, listar, …)
scripts/publicar.py             o que o GitHub roda a cada 15 min
scripts/verificar_token.py      conferência semanal do token
scripts/regras.py               validações (tamanho da legenda, hashtags, OAB)
.github/workflows/              os dois agendamentos
fila/ publicando/ publicados/ erros/   estado de cada post (um .json por post)
midia/<id>/                     as imagens públicas de cada post
status/token.json               resultado da última conferência do token
```

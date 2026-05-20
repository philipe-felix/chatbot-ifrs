# API Chatbot WhatsApp - IFRS

Backend em FastAPI para gerenciamento automático de atendimento via WhatsApp, desenvolvido para o ecossistema do IFRS. O sistema gerencia o cadastro de interessados, bases de cursos (iniciando com Técnico em Enfermagem) e garante o consentimento focado na LGPD.

## Funcionalidades
- Webhook preparado para WhatsApp (Meta, Twilio, Z-API)
- Fluxo de atendimento automático
- Cadastro e gestão de interessados
- Conformidade com LGPD
- Rotas administrativas e base de editais editável

## Como rodar localmente

1. Clone o repositório:
   ```bash
   git clone [https://github.com/philipe-felix/chatbot-ifrs.git](https://github.com/philipe-felix/chatbot-ifrs.git)

2. Acesse a pasta do projeto: 
Bash
cd chatbot-ifrs

3. Crie e ative um ambiente virtual:

Bash
python -m venv venv

# No Windows (PowerShell):
venv\Scripts\activate

# No Linux/Mac:
source venv/bin/activate
Instale as dependências:

Bash
pip install -r requirements.txt
Configure as variáveis de ambiente:

Crie um arquivo chamado .env na raiz do projeto.

Adicione as seguintes variáveis (você pode deixar os dados do WhatsApp vazios para rodar em modo de desenvolvimento local):

Snippet de código
DATABASE_URL=sqlite:///./ifrs_chatbot.db
VERIFY_TOKEN=seu_token_secreto_aqui
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
PROVIDER=meta
Inicie o servidor:

Bash
python -m uvicorn backend_chatbot_ifrs_whatsapp:app --reload
Acesse a documentação interativa para testar as rotas da API em: http://localhost:8000/docs
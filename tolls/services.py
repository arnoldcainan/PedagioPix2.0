import requests
import qrcode
import base64
from io import BytesIO
from django.conf import settings
from datetime import timedelta
from django.utils import timezone


class BancoBrasilPixService:
    def __init__(self):
        # Puxando as credenciais do settings.py (que por sua vez lê do .env)
        self.client_id = settings.BB_CLIENT_ID
        self.client_secret = settings.BB_CLIENT_SECRET
        self.gw_dev_app_key = settings.BB_GW_DEV_APP_KEY

        # URLs de Homologação (Teste) do BB
        self.auth_url = "https://oauth.hm.bb.com.br/oauth/token"
        self.pix_url = f"https://api.hm.bb.com.br/pix/v2/cob?gw-dev-app-key={self.gw_dev_app_key}"

    def _obter_token(self):
        """Autentica na API do BB e retorna o Bearer Token."""
        data = {
            "grant_type": "client_credentials",
            "scope": "cob.write pix.read"
        }
        auth = (self.client_id, self.client_secret)

        try:
            response = requests.post(self.auth_url, data=data, auth=auth, timeout=10)
            response.raise_for_status()  # Lança exceção se o status não for 2xx
            return response.json().get("access_token")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Falha ao obter token do BB: {str(e)}")

    def criar_cobranca(self, passagem, expiracao_segundos=3600):
        """Cria a cobrança imediata atrelada a uma passagem e retorna os dados do PIX."""
        token = self._obter_token()

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        payload = {
            "calendario": {
                "expiracao": expiracao_segundos
            },
            "devedor": {
                "cnpj": "12345678000195",  # Substitua pelo CNPJ real da concessionária depois
                "nome": "Empresa de Pedágio SA"
            },
            "valor": {
                "original": str(passagem.valor)
            },
            "chave": "9e881f18-cc66-4fc7-8f2c-a795dbb2bfc1",  # Substitua pela chave PIX real cadastrada no BB
            "solicitacaoPagador": f"Pagamento de pedágio - Placa: {passagem.placa}",
            "infoAdicionais": [
                {
                    "nome": "Placa",
                    "valor": passagem.placa
                }
            ]
        }

        try:
            response = requests.post(self.pix_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            resposta_json = response.json()
            pix_copia_e_cola = resposta_json.get("pixCopiaECola")

            if not pix_copia_e_cola:
                raise Exception("A resposta da API não conteve o payload do PIX (pixCopiaECola).")

            # Gera a imagem do QR Code em Base64
            qr_encoded = self._gerar_qrcode_base64(pix_copia_e_cola)

            # Calcula a data exata de expiração baseada no timezone atual
            data_expiracao = timezone.now() + timedelta(seconds=expiracao_segundos)

            return {
                "txid": resposta_json.get("txid"),
                "payload": pix_copia_e_cola,
                "qr_code_base64": qr_encoded,
                "data_expiracao": data_expiracao
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na comunicação com a API de Cobrança do BB: {str(e)}")

    def _gerar_qrcode_base64(self, payload):
        """Gera o QR Code em memória e retorna a string codificada em base64."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")

        return base64.b64encode(buffer.getvalue()).decode("utf-8")
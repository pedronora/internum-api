from typing import TypedDict

PRIMARY_COLOR = '#0d6efd'
SECONDARY_COLOR = '#6c757d'
INFO_COLOR = '#0dcaf0'
TEXT_COLOR = '#212529'
SURFACE_COLOR = '#f8f9fa'
BORDER_COLOR = '#dee2e6'
INFO_BG_COLOR = '#cff4fc'


class PasswordResetPayload(TypedDict):
    user_name: str
    reset_link: str
    requested_at: str
    expire_minutes: int


def password_reset_template(payload: PasswordResetPayload) -> str:
    return f"""
    <html>
      <body
        style="margin: 0; padding: 24px 12px; background: {SURFACE_COLOR};"
      >
        <table
          role="presentation"
          width="100%"
          cellspacing="0"
          cellpadding="0"
        >
          <tr>
            <td align="center">
              <table
                role="presentation"
                width="100%"
                cellspacing="0"
                cellpadding="0"
                style="
                  max-width: 640px;
                  background: #ffffff;
                  border: 1px solid {BORDER_COLOR};
                  border-radius: 10px;
                  overflow: hidden;
                  font-family: Arial, sans-serif;
                "
              >
                <tr>
                  <td
                    style="padding: 20px 24px; background: {PRIMARY_COLOR};"
                  >
                    <h2
                      style="
                        margin: 0;
                        color: #ffffff;
                        font-size: 20px;
                        font-weight: 700;
                      "
                    >
                      Recuperação de Senha
                    </h2>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 24px;">
                    <p
                      style="
                        margin: 0 0 10px;
                        color: {TEXT_COLOR};
                        font-size: 15px;
                      "
                    >
                      Olá, <strong>{payload['user_name']}</strong>.
                    </p>
                    <p
                      style="
                        margin: 0 0 20px;
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        line-height: 1.6;
                      "
                    >
                      Você solicitou a redefinição de senha da sua conta no
                      <strong>Internum</strong>. Clique no botão abaixo para
                      criar uma nova senha.
                    </p>

                    <p style="margin: 0 0 20px; text-align: center;">
                      <a
                        href="{payload['reset_link']}"
                        style="
                          display: inline-block;
                          padding: 12px 24px;
                          border-radius: 6px;
                          background: {PRIMARY_COLOR};
                          color: #ffffff;
                          text-decoration: none;
                          font-size: 15px;
                          font-weight: 700;
                        "
                      >
                        Redefinir Senha
                      </a>
                    </p>

                    <p
                      style="
                        margin: 0;
                        padding: 12px 14px;
                        border-radius: 6px;
                        background: {INFO_BG_COLOR};
                        color: {TEXT_COLOR};
                        font-size: 14px;
                        line-height: 1.6;
                      "
                    >
                      <strong style="color: {INFO_COLOR};">
                        Expiração do Link:
                      </strong>
                      {payload['expire_minutes']} minutos, a partir de
                      {payload['requested_at']}.
                    </p>
                    <p
                      style="
                        margin: 12px 0 0;
                        color: {SECONDARY_COLOR};
                        font-size: 13px;
                        line-height: 1.5;
                      "
                    >
                      Se você não solicitou essa alteração, ignore este e-mail.
                    </p>
                  </td>
                </tr>

                <tr>
                  <td
                    style="
                      padding: 14px 24px;
                      border-top: 1px solid {BORDER_COLOR};
                      color: {SECONDARY_COLOR};
                      font-size: 12px;
                      line-height: 1.5;
                    "
                  >
                    Esta é uma mensagem automática do sistema Internum -
                    1º SRI de Cascavel/PR.
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

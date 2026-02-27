from typing import TypedDict

PRIMARY_COLOR = '#0d6efd'
SECONDARY_COLOR = '#6c757d'
INFO_COLOR = '#0dcaf0'
TEXT_COLOR = '#212529'
SURFACE_COLOR = '#f8f9fa'
BORDER_COLOR = '#dee2e6'
INFO_BG_COLOR = '#cff4fc'


class LoanEmailPayload(TypedDict):
    title: str
    user_name: str
    intro_message: str
    event_label: str
    event_value: str
    book_title: str
    book_author: str


def _build_loan_email(
    payload: LoanEmailPayload,
    due_date_str: str | None = None,
) -> str:
    due_date_row = ''
    if due_date_str:
        due_date_row = (
            '<tr>'
            '<td style="padding: 8px 0; '
            f'color: {SECONDARY_COLOR}; width: 140px;">'
            'Devolver até'
            '</td>'
            f'<td style="padding: 8px 0; color: {TEXT_COLOR};"><strong>'
            f'{due_date_str}'
            '</strong></td>'
            '</tr>'
        )

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
                      {payload['title']}
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
                      {payload['intro_message']}
                    </p>

                    <table
                      role="presentation"
                      width="100%"
                      cellspacing="0"
                      cellpadding="0"
                      style="
                        margin-bottom: 16px;
                        background: {SURFACE_COLOR};
                        border: 1px solid {BORDER_COLOR};
                        border-radius: 8px;
                        padding: 14px 16px;
                      "
                    >
                      <tr>
                        <td
                          style="
                            padding: 8px 0;
                            color: {SECONDARY_COLOR};
                            width: 140px;
                          "
                        >
                          Título
                        </td>
                        <td style="padding: 8px 0; color: {TEXT_COLOR};">
                          <strong>{payload['book_title']}</strong>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding: 8px 0; color: {SECONDARY_COLOR};">
                          Autor
                        </td>
                        <td style="padding: 8px 0; color: {TEXT_COLOR};">
                          <strong>{payload['book_author']}</strong>
                        </td>
                      </tr>
                      {due_date_row}
                    </table>

                    <p
                      style="
                        margin: 0;
                        padding: 12px 14px;
                        border-radius: 6px;
                        background: {INFO_BG_COLOR};
                        color: {TEXT_COLOR};
                        font-size: 14px;
                      "
                    >
                      <strong style="color: {INFO_COLOR};">
                        {payload['event_label']}:
                      </strong>
                      {payload['event_value']}
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


def loan_request_template(
    user_name: str,
    book_title: str,
    book_author: str,
    requested_str: str,
) -> str:
    return _build_loan_email(
        payload={
            'title': 'Confirmação de Solicitação de Empréstimo',
            'user_name': user_name,
            'intro_message': (
                'Seu pedido de empréstimo foi registrado com sucesso e será '
                'avaliado pela coordenação.'
            ),
            'event_label': 'Data/Hora da Solicitação',
            'event_value': requested_str,
            'book_title': book_title,
            'book_author': book_author,
        }
    )


def loan_cancel_template(
    user_name: str,
    book_title: str,
    book_author: str,
    canceled_str: str,
) -> str:
    return _build_loan_email(
        payload={
            'title': 'Confirmação de Cancelamento de Empréstimo',
            'user_name': user_name,
            'intro_message': 'Você cancelou seu pedido de empréstimo.',
            'event_label': 'Data/Hora do Cancelamento',
            'event_value': canceled_str,
            'book_title': book_title,
            'book_author': book_author,
        }
    )


def loan_approve_template(
    user_name: str,
    book_title: str,
    book_author: str,
    due_date_str: str,
    requested_str: str,
) -> str:
    return _build_loan_email(
        payload={
            'title': 'Confirmação de Aprovação de Empréstimo',
            'user_name': user_name,
            'intro_message': (
                'Seu pedido de empréstimo foi aprovado pela coordenação.'
            ),
            'event_label': 'Data/Hora da Solicitação',
            'event_value': requested_str,
            'book_title': book_title,
            'book_author': book_author,
        },
        due_date_str=due_date_str,
    )


def loan_return_template(
    user_name: str,
    book_title: str,
    book_author: str,
    returned_str: str,
) -> str:
    return _build_loan_email(
        payload={
            'title': 'Confirmação de Devolução de Empréstimo',
            'user_name': user_name,
            'intro_message': 'Seu empréstimo foi devolvido com sucesso.',
            'event_label': 'Data/Hora da Devolução',
            'event_value': returned_str,
            'book_title': book_title,
            'book_author': book_author,
        }
    )


def loan_reject_template(
    user_name: str,
    book_title: str,
    book_author: str,
    reject_str: str,
) -> str:
    return _build_loan_email(
        payload={
            'title': 'Informação de Rejeição de Empréstimo',
            'user_name': user_name,
            'intro_message': (
                'Seu empréstimo foi rejeitado pela coordenação. Para maiores '
                'detalhes, procure seu coordenador.'
            ),
            'event_label': 'Data/Hora da Rejeição',
            'event_value': reject_str,
            'book_title': book_title,
            'book_author': book_author,
        }
    )

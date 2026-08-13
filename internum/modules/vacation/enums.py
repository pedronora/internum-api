from enum import StrEnum


class VacationAccrualStatus(StrEnum):
    ACQUISITIVE = 'acquisitive'  # Período aquisitivo em andamento
    CONCESSIVE = 'concessive'  # Período concessivo (pode gozar)
    EXPIRED = 'expired'  # Concessivo acabou sem gozo
    CLOSED = 'closed'  # Regularizado (gozou/pagou dobro)


class VacationGrantType(StrEnum):
    NORMAL = 'normal'  # Gozo normal aprovado
    RETROACTIVE = 'retroactive'  # Gozo atrasado cadastrado pelo admin
    DOUBLE_PAYMENT = 'double_payment'  # Pagamento em dobro (não gozou)


class VacationGrantStatus(StrEnum):
    GRANTED = 'granted'  # Aprovado, reservado
    IN_PROGRESS = 'in_progress'  # Período de gozo iniciado
    FRUITED = 'fruited'  # RH confirmou fruição
    CANCELLED = 'cancelled'  # Cancelado
    PAID_DOUBLE = 'paid_double'  # Pagamento em dobro confirmado


class VacationPeriodType(StrEnum):
    MAIN = 'main'  # Período principal, >= 14 dias
    COMPLEMENTARY = 'complementary'  # Período complementar, 5 a 13 dias


class VacationRequestStatus(StrEnum):
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'


class VacationAlertType(StrEnum):
    EXPIRED = 'expired'  # Concessivo já expirou, precisa regularizar
    ABOUT_TO_EXPIRE = 'about_to_expire'  # Concessivo vence em até 30 dias
    PENDING = 'pending'  # Concessivo em aberto, sem férias marcadas

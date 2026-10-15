"""When a driver's phone says something was done (a sale, an expense, a loss, a payment, boxes): the time is
checked here, and the day it falls on is checked by the caller (D-133)."""

import datetime as dt

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

# A phone may be a little fast or slow: within this margin of the server's clock, the server's own time is used.
CLOCK_MARGIN = dt.timedelta(minutes=5)


def moment_from_phone(made_at: dt.datetime | None, *, field: str = "sold_at") -> dt.datetime | None:
    """When a driver's record is dated, from the time their phone says it was made (D-133). The phone is not
    trusted: the time is checked here, and the day it falls on is checked by the caller (the driver's truck
    that day, a day the office has not approved).

    Nothing sent, or a time within `CLOCK_MARGIN` of the server's clock, before or after: None, the record is
    made now and the server's own clock dates it, so a phone a little fast or slow changes nothing. Further in
    the future: refused on `field`. Earlier: that time, for a record kept on the phone without connection and
    sent later.
    """
    if made_at is None:
        return None
    now = timezone.now()
    if made_at > now + CLOCK_MARGIN:
        raise ValidationError(
            {
                field: _("Cette saisie est datée dans le futur (%(when)s) : vérifiez la date et l'heure du téléphone.")
                % {"when": date_format(timezone.localtime(made_at), "d/m/Y H:i")}
            }
        )
    if made_at >= now - CLOCK_MARGIN:
        return None
    return made_at

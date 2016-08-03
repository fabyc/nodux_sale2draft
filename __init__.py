#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *

def register():
    Pool.register(
        Sale,
        DraftSaleStart,
        module='nodux_sale2draft', type_='model')
    Pool.register(
        DraftSale,
        module='nodux_sale2draft', type_='wizard')

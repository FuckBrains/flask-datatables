"""
    flask.ext.restless.views
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Provides the following view classes, subclasses of
    :class:`flask.MethodView` which provide generic endpoints for interacting
    with an entity of the database:

    :class:`flask.ext.restless.views.API`
      Provides the endpoints for each of the basic HTTP methods. This is the
      main class used by the
      :meth:`flask.ext.restless.manager.APIManager.create_api` method to create
      endpoints.

    :class:`flask.ext.restless.views.FunctionAPI`
      Provides a :http:method:`get` endpoint which returns the result of
      evaluating some function on the entire collection of a given model.

    :copyright: 2011 by Lincoln de Sousa <lincoln@comum.org>
    :copyright: 2012, 2013, 2014, 2015 Jeffrey Finkelstein
                <jeffrey.finkelstein@gmail.com> and contributors.
    :license: GNU AGPLv3+ or BSD

"""
from __future__ import division

from collections import defaultdict
from functools import wraps
import math
import warnings
import json

from sqlalchemy import Column
from sqlalchemy.exc import DataError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.query import Query
from werkzeug.urls import url_quote_plus

from flask_datatables.views.apihelpers import count
from flask_datatables.views.apihelpers import evaluate_functions
from flask_datatables.views.apihelpers import get_by
from flask_datatables.views.apihelpers import get_columns
from flask_datatables.views.apihelpers import get_or_create
from flask_datatables.views.apihelpers import get_related_model
from flask_datatables.views.apihelpers import get_relations
from flask_datatables.views.apihelpers import has_field
from flask_datatables.views.apihelpers import is_like_list
from flask_datatables.views.apihelpers import partition
from flask_datatables.views.apihelpers import primary_key_name
from flask_datatables.views.apihelpers import query_by_primary_key
from flask_datatables.views.apihelpers import session_query
from flask_datatables.views.apihelpers import strings_to_dates
from flask_datatables.views.apihelpers import to_dict
from flask_datatables.views.apihelpers import upper_keys
from flask_datatables.views.apihelpers import get_related_association_proxy_model
from flask_datatables.views.search import create_query
from flask_datatables.views.search import search as qsearch



def search(session, model, params):
    """Defines a generic search function for the database model.

    If the query string is empty, or if the specified query is invalid for
    some reason (for example, searching for all person instances with), the
    response will be the JSON string ``{"objects": []}``.

    To search for entities meeting some criteria, the client makes a
    request to :http:get:`/api/<modelname>` with a query string containing
    the parameters of the search. The parameters of the search can involve
    filters. In a filter, the client specifies the name of the field by
    which to filter, the operation to perform on the field, and the value
    which is the argument to that operation. In a function, the client
    specifies the name of a SQL function which is executed on the search
    results; the result of executing the function is returned to the
    client.

    The parameters of the search must be provided in JSON form as the value
    of the ``q`` request query parameter. For example, in a database of
    people, to search for all people with a name containing a "y", the
    client would make a :http:method:`get` request to ``/api/person`` with
    query parameter as follows::

        q={"filters": [{"name": "name", "op": "like", "val": "%y%"}]}

    If multiple objects meet the criteria of the search, the response has
    :http:status:`200` and content of the form::

    .. sourcecode:: javascript

       {"objects": [{"name": "Mary"}, {"name": "Byron"}, ...]}

    If the result of the search is a single instance of the model, the JSON
    representation of that instance would be the top-level object in the
    content of the response::

    .. sourcecode:: javascript

       {"name": "Mary", ...}

    For more information SQLAlchemy operators for use in filters, see the
    `SQLAlchemy SQL expression tutorial
    <http://docs.sqlalchemy.org/en/latest/core/tutorial.html>`_.

    The general structure of request data as a JSON string is as follows::

    .. sourcecode:: javascript

       {
         "single": true,
         "order_by": [{"field": "age", "direction": "asc"}],
         "limit": 2,
         "offset": 1,
         "disjunction": true,
         "filters":
           [
             {"name": "name", "val": "%y%", "op": "like"},
             {"name": "age", "val": [18, 19, 20, 21], "op": "in"},
             {"name": "age", "op": "gt", "field": "height"},
             ...
           ]
       }

    For a complete description of all possible search parameters and
    responses, see :ref:`searchformat`.

    """
    # try to get search query from the request query parameters
    search_params = json.loads(params['q'])

    # resolve date-strings as required by the model
    for param in search_params.get('filters', list()):
        if 'name' in param and 'val' in param:
            query_model = model
            query_field = param['name']
            if '__' in param['name']:
                fieldname, relation = param['name'].split('__')
                submodel = getattr(model, fieldname)
                if isinstance(submodel, InstrumentedAttribute):
                    query_model = submodel.property.mapper.class_
                    query_field = relation
                elif isinstance(submodel, AssociationProxy):
                    # For the sake of brevity, rename this function.
                    get_assoc = get_related_association_proxy_model
                    query_model = get_assoc(submodel)
                    query_field = relation
            to_convert = {query_field: param['val']}
            try:
                result = strings_to_dates(query_model, to_convert)
            except ValueError as exception:
                current_app.logger.exception(str(exception))
                return dict(message='Unable to construct query'), 400
            param['val'] = result.get(query_field)

    query = qsearch(session, model, search_params)
    return query


from __future__ import print_function
from collections import namedtuple
from sqlalchemy import and_, or_, desc, asc, alias
from sqlalchemy.orm import relation, backref, synonym, outerjoin, join, eagerload, relationship, validates, aliased
import inspect
from querystring_parser import parser
from flask import request, current_app
from flask_datatables import views
from flask_datatables.views import apihelpers as helpme
import sys

if sys.version_info.major == 3:
    unicode = str

def log_debug(message):
    if current_app and current_app.debug:
        print(message, file=sys.stderr)

def get_resource(Resource, Table, Session, basepath="/"):
    """ Return a flask-restful datatables resource for SQLAlchemy

        This function returns a class subclassed from Flask-Restless Resource
        that is set up for GET only restful requests prepared for datatables
        and enhanced with Flask-Restless filtering

        Use this function inside your flask-restful app to create
        datatables endpoints for your SA tables

        ARGS:
            Resource    (class):    Flask-Restful Resource
            Table       (class):    SA Table class
            Session     (inst):     SA Session instance
            basepath    (str):      Base path to put endpoint

        EXAMPLE:
            Assuming you already have your SA Session object as Session

            app = Flask(__name__)
            api = Api(app)
            resource, path, endpoint = get_resource(Resource, tableObj, Session, basepath="/")
            api.add_resource(resource, path, endpoint=endpoint)


    """
    class TmpResource(Resource):
        def get(self):
            # parse the url args into a dict
            parsed = parser.parse(request.query_string)

            # column names for this table
            dtcols = get_columns(Table, parsed)
            #for col in dtcols:
            #    print col

            # pre build the query so we can add filters to it here
            try:
                query = Table.query  # Flask-SQLAlchemy
            except:
                query = Session.query(Table)  # vanilla SQLALchemy

            # check if we are filtering the rows some how
            # this uses the restless view code
            if 'q' in parsed.keys():
                query = views.search(Session, Table, parsed)

            total_query = 'select count(id) from {0}'.format(Table.__tablename__)
            total_records = Session.execute(total_query).first()
            if total_records:
                total_recs = int(total_records[0])
                log_debug("total recs for table {} is {}".format(Table.__tablename__, total_recs))
            else:
                total_recs = 0

            log_debug(str(query))
            # get our DataTable object
            dtobj = DataTable( parsed, Table, query, dtcols, total_recs)
            # return the query result in json

            return dtobj.json()
    # return stuff that can be passed to api.add_resource
    return (TmpResource, '%s%s' % (basepath,Table.__tablename__), '%s%s' % (basepath,Table.__tablename__))



def get_columns(Table, parsed):
    """
        Helper function that just builds the tuples datatables needs for the columns
    """
    # column names for this table
    dtcols = []
    # put them in, it's just a list of (col_name, col_name)
    for col in parsed['columns'].values():
        col = col['data']
        colname = col
        if col:
            if '__' in col:
                col = col.replace('__', '.')
            dtcols.append((colname, col, lambda i: u"{}".format(i)))
    return dtcols



BOOLEAN_FIELDS = (
    "search.regex", "orderable", "regex"
)


DataColumn = namedtuple("DataColumn", ("name", "model_name", "filter"))


class DataTablesError(ValueError):
    pass


class DataTable(object):
    def __init__(self, params, model, query, columns, total_recs=0):
        self.params = params
        self.model = model
        self.query = query
        self.data = {}
        self.columns = []
        self.columns_dict = {}
        self.total_recs = total_recs

        for col in columns:
            name, model_name, filter_func = None, None, None

            if isinstance(col, DataColumn):
                d = col
                self.columns.append(d)
            elif isinstance(col, tuple):
                # col is either 1. (name, model_name), 2. (name, filter) or 3. (name, model_name, filter)
                if len(col) == 3:
                    name, model_name, filter_func = col
                elif len(col) == 2:
                    # Work out the second argument. If it is a function then it's type 2, else it is type 1.
                    if callable(col[1]):
                        name, filter_func = col
                        model_name = name
                    else:
                        name, model_name = col
                else:
                    raise ValueError("Columns must be a tuple of 2 to 3 elements")
                d = DataColumn(name=name, model_name=model_name, filter=filter_func)
                self.columns.append(d)
            else:
                # It's just a string
                name, model_name = col, col
                d = DataColumn(name=name, model_name=model_name, filter=None)
                self.columns.append(d)
            self.columns_dict[d.name] = d

        # get only unique relationships to join
        # fix for when there are multiple columns within the same joined table
        # only eliminates warnings but still...
        seenjoins = []
        seencols = []
        for column in (col for col in self.columns if "." in col.model_name):
            # of of table user model_name can look like family.address.city or more/less dots
            # joincols would be ['family', 'address'] leaving out the actual column, city
            log_debug("column: {}".format(column))
            joincols = column.model_name.split(".")[:-1]
            log_debug("joincols: {}".format(joincols))

            curtable = helpme.get_related_model(self.model, joincols[0]).__tablename__
            log_debug("curtable: {}, joincols: {}".format(curtable, joincols))
            # join the first column, which is off of our class
            # check if 'family' is joined already
            if joincols[0] not in seencols and curtable not in seenjoins:
                seenjoins.append(curtable)
                log_debug("seenjoins is now: {}".format(seenjoins))
                # append family to seencols so we don't rejoin later
                log_debug("appending {} to seencols".format(joincols[0]))
                seencols.append(joincols[0])
                # outer join family
                log_debug("joincols[0] is {}".format(joincols[0]))
                self.query = self.query.join(joincols[0], isouter=True)
                log_debug("query is now: {}".format(self.query))

            # check if we are doing more than the simple user.famly join (in this example user.family.address)
            if len(joincols) > 1:

                # copy our table to curmodel
                curmodel = self.model
                log_debug("curmodel is now: {}".format(curmodel.__tablename__))

                # we don't want to do this to the last item ([:-1])
                for i, joincol in enumerate(joincols[:-1]):

                    # helper method to get the table for the current related model
                    curmodel = helpme.get_related_model(curmodel, joincol)
                    log_debug("i -> {}, joincol -> {}".format(i, joincol))

                    # we don't want to do this for columns we already did also
                    if joincol not in seencols:
                        log_debug("joincol not in seencols: {}, {}".format(joincol, seencols))
                        seencols.append(joincol)
                    if joincols[i+1] not in seencols:
                        log_debug("joincols[i+1] not in seencols: {}, {}".format(joincols[i+1], seencols))
                        # get the tablename so we can log that we joined with it
                        joinmodel = aliased(helpme.get_related_model(curmodel, joincols[i+1]))
                        if joinmodel.__tablename__ in seenjoins:
                            continue
                        # append to seen joins
                        seenjoins.append(joinmodel.__tablename__)
                        # get the remote table object like User.domus rather than XenDomU like above aliased will pull out
                        joinmodel = getattr(curmodel, joincols[i+1])
                        log_debug("joinmodel: {}".format(joinmodel))
                        #self.query = self.query.join(getattr(curmodel, joincols[i+1]), isouter=True)
                        self.query = self.query.join(joinmodel, isouter=True)
                        seencols.append(joincols[i+1])
        log_debug(str(self.query))

    @staticmethod
    def coerce_value(key, value):
        try:
            return int(value)
        except ValueError:
            if key in BOOLEAN_FIELDS:
                return value == "true"

        return value

    def get_integer_param(self, param_name):
        if param_name not in self.params:
            raise DataTablesError("Parameter {} is missing".format(param_name))

        try:
            return int(self.params[param_name])
        except ValueError:
            raise DataTablesError("Parameter {} is invalid".format(param_name))

    def add_data(self, **kwargs):
        self.data.update(**kwargs)

    def json(self):
        try:
            return self._json()
        except DataTablesError as e:
            return {
                "error": str(e)
            }

    def get_column(self, column):
        if "." in column.model_name:
            column_path = column.model_name.split(".")

            # get the column we are getting
            column_name = column_path[-1]

            # the path to the column
            column_path = column_path[:-1]
            curmodel = self.model
            for column in column_path:
                curmodel = helpme.get_related_model(curmodel, column)
            model_column = getattr(curmodel, column_name)
        else:
            model_column = getattr(self.model, column.model_name)

        return model_column

    def _json(self):
        draw = self.get_integer_param("draw")
        start = self.get_integer_param("start")
        length = self.get_integer_param("length")

        columns = self.params["columns"]
        ordering = self.params["order"]
        search = self.params["search"]

        query = self.query
        total_records = query.count()
        #total_records = self.total_recs

        # handle searches here rather than using the old searchable function
        if search.get("value", None):
            valuestr = '%%%s%%' % str(search["value"])

            # this builds a list of .like() comparisons for the
            # value passed and every column so it's a global search
            orlist = []
            non_searchable = []
            for col, row in self.params["columns"].items():
                if not row['searchable']:
                    non_searchable.append(row['data'])
                elif str(row['searchable']).lower() == 'false':
                    non_searchable.append(row['data'])
            log_debug({"non_searchable":non_searchable})
            #log_debug({"searchcols":self.columns})
            for searchcol in self.columns:
                if isinstance(searchcol, DataColumn) and searchcol.name in non_searchable:
                    continue
                model_column = self.get_column(searchcol)
                orlist.append(model_column.like(unicode(valuestr)))
            #log_debug({"orlist":orlist})
            # modify the query then return it
            query = query.filter(and_(or_(*orlist)))


        for order in ordering.values():
            direction, column = order["dir"], order["column"]
            column = int(column)

            if column not in columns:
                raise DataTablesError("Cannot order {}: column not found".format(column))

            if not columns[column]["orderable"]:
                continue

            column_name = columns[column]["data"]
            column = self.columns_dict[column_name]

            model_column = self.get_column(column)

            if isinstance(model_column, property):
                raise DataTablesError("Cannot order by column {} as it is a property".format(column.model_name))

            query = query.order_by(desc(model_column) if direction == "desc" else asc(model_column))

        filtered_records = query.count()
        query = query.slice(start, start + length)

        retval = {
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": [
                self.output_instance(instance) for instance in query.all()
            ]
        }
        #print retval
        return retval

    def output_instance(self, instance):
        returner = {
            key.name.replace('.', '__'): self.get_value(key, instance) for key in self.columns
        }

        if self.data:
            returner["DT_RowData"] = {
                k: v(instance) for k, v in self.data.items()
            }

        return returner

    def get_value(self, key, instance):
        attr = key.model_name
        if "." in attr:
            tmp_list=attr.split(".")
            attr=tmp_list[-1]
            for sub in tmp_list[:-1]:
                oldinstance = instance
                try:
                    instance = getattr(instance, sub)
                except Exception:
                    instance = oldinstance
                    break

        if instance:
            if key.filter is not None:
                r = key.filter(getattr(instance, attr))
            else:
                r = getattr(instance, attr)
        else:
            r = ""

        return r() if inspect.isroutine(r) else r

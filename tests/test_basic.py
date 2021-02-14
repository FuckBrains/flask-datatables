from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import faker
from querystring_parser import parser
import json
from .models import *
from flask_datatables import *
import os


class TestDataTables:
    def setup_method(self, method):
        if os.path.isfile('testdb.db'):
            os.unlink('testdb.db')
        engine = create_engine('sqlite:///testdb.db', echo=True)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        self.session = Session()

        # initialize DB with 10 fake items
        if not self.session.query(User).all():
            self.make_data(10)

    def make_data(self, user_count):
        f = faker.Faker()
        users = []

        for i in range(user_count):
            user, addr = self.make_user(f.name(), f.street_address())
            users.append(user)

        self.session.add_all(users)
        self.session.commit()

    def make_user(self, name, address):
        addr = Address()
        addr.description = address

        u = User()
        u.full_name = name
        u.address = addr

        return u, addr

    def make_params_str(self, order=None, search=None, start=0, length=10, urlfilter=None,
                    columns=("id", "name", "address")):
        x = {
            "draw": "1",
            "search[value]": "",
            "search[regex]": "false",
            "order[0][column]": "1",
            "order[0][dir]": "asc",
            "start": str(start),
            "length": str(length)
        }

        for i, item in enumerate(columns):
            b = "columns[{}]".format(i)
            x[b + "[data]"] = item
            x[b + "[name]"] = ""
            x[b + "[searchable]"] = "true"
            x[b + "[orderable]"] = "true"
            x[b + "[search][value]"] = ""
            x[b + "[search][regex]"] = "false"

        for i, item in enumerate(order or []):
            for key, value in item.items():
                x["order[{}][{}]".format(i, key)] = str(value)

        if search:
            for key, value in search.items():
                x["search[{}]".format(key)] = str(value)

        # this mimics an actual request
        y = ""
        if urlfilter:
            y += "q={}&".format(urlfilter)
        y += "{}={}&".format('draw', x['draw'])
        y += "&".join("{}={}".format(k, v) for k, v in x.items() if k != 'draw')

        return y

    def make_params(self, **kwargs):
        y = self.make_params_str(**kwargs)
        # use parser to parse the request into a dict we can use in DataTable
        return parser.parse(y)



    def test_basic_function(self):
        req = self.make_params()

        table = DataTable(req, User, self.session.query(User), [
            "id",
            ("name", "full_name"),
            ("address", "address.description"),
        ])

        x = table.json()

        assert len(x["data"]) == 10

    def test_relation_ordering(self):
        u1, addr_asc = self.make_user("SomeUser", "0" * 15)
        u2, addr_desc = self.make_user("SomeOtherUser", "z" * 15)
        self.session.add_all((u1, u2))
        self.session.commit()

        req = self.make_params(order=[{"column": 2, "dir": "desc"}])
        table = DataTable(req,
                          User,
                          self.session.query(User),
                          [
                              "id",
                              ("name", "full_name"),
                              ("address", "address.description")
                          ])
        result = table.json()
        assert result["data"][0]["address"] == addr_desc.description

        req = self.make_params(order=[{"column": 2, "dir": "asc"}])
        table = DataTable(req,
                          User,
                          self.session.query(User),
                          [
                              "id",
                              ("name", "full_name"),
                              ("address", "address.description")
                          ])
        result = table.json()
        assert result["data"][0]["address"] == addr_asc.description

    def test_relation_urlfilter(self):
        """ This tests the flask-restless integrated filtering
            In this test case we are filtering on a relationship.
            Look at filtering in flask-restless documentation for more
            filter options
        """
        u1, addr_a = self.make_user("userOne", "a")
        u2, addr_b = self.make_user("userTwo", "b")
        self.session.add_all((u1, u2))
        self.session.commit()

        # create a filter (flask-restless style, key will be 'q', set in the make_params function
        urlfilter = json.dumps({"filters":[{"name": "address__description", "op": "has", "val": "a"}]})

        # this is a fake request as we pretend to have gotten from datatables js
        req = self.make_params(urlfilter=urlfilter)

        # if q is in the request.keys() we do the resltess filtering on the query
        if 'q' in req.keys():
            query = views.search(self.session, User, req)

        # build the datatable with the query
        table = DataTable(req, User, query, [
            "id",
            ("name", "full_name"),
            ("address", "address.description")
            ])

        # get result
        result = table.json()
        assert result["data"][0]["address"] == addr_a.description
        assert len(result["data"]) == 1

        # same for b
        urlfilter = json.dumps({"filters":[{"name": "address__description", "op": "has", "val": "b"}]})
        req = self.make_params(urlfilter=urlfilter)
        if 'q' in req.keys():
            query = views.search(self.session, User, req)

        table = DataTable(req, User, query, [
            "id",
            ("name", "full_name"),
            ("address", "address.description")
            ])
        result = table.json()
        assert result["data"][0]["address"] == addr_b.description
        assert len(result["data"]) == 1


    def test_error(self):
        """ make sure we are able to capture failures... """
        req = self.make_params()
        req["start"] = "invalid"

        table = DataTable(req,
                          User,
                          self.session.query(User),
                          ["id"])
        assert "error" in table.json()

        req = self.make_params()
        del req["start"]

        table = DataTable(req,
                          User,
                          self.session.query(User),
                          ["id"])
        assert "error" in table.json()


    def test_search(self):
        """ Test the basic search functionality.
            This method is not required but here to show that it works
            The main search/filter method is to use the ?q={"filters":[...]}
            method from flask-restless that I have incorporated which
            provides much more flexibility in searching deep relations
        """
        user, addr = self.make_user("Silly Sally", "Silly Sally Road")
        user2, addr2 = self.make_user("Silly Billy", "Silly Billy Road")
        self.session.add_all((user, user2))
        self.session.commit()

        req = self.make_params(search={
            "value": "Silly Sally"
        })

        table = DataTable(req, User, self.session.query(User), [("name", "full_name")])
        results = table.json()
        assert len(results["data"]) == 1

        req = self.make_params(search={
            "value": "Silly"
        })

        table = DataTable(req, User, self.session.query(User), [("name", "full_name")])
        results = table.json()
        assert len(results["data"]) == 2


    def test_datatables(self):
        """ Test the datatables function get_resource """
        import flask_restful as rest
        from flask import current_app, Flask
        app = current_app or Flask('test')
        api = rest.Api(app)

        Resource, path, endpoint = get_resource(rest.Resource, User, self.session, basepath='/api/')
        api.add_resource(Resource, path, endpoint=endpoint)

        client = app.test_client()
        params = self.make_params_str(columns=('id', 'full_name', 'created_at'))
        response = client.get('/api/users?%s' % params)
        assert response.status_code == 200

        str_response = response.data.decode('utf-8')
        obj = json.loads(str_response)
        assert len(obj['data']) == 10

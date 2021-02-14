
====================
Flask-restful only version of orf/datatables with Flask-restless style filtering
====================

Additional Functionality
------------
One thing I needed to do so that this would support our needs internally is
to support arbitrary join depth to be able to do search and sort functionality
on the results. With Orf's version, I was only able to order by or search on 2
levels deep of a query result. Now that level is arbitrary such that you can
provide a column on say a Subnet table that is associated with a location
through relations like subnet.vlan.switch.rack.location and make the location name
filterable AND orderable with just "vlan__switch__rack__location__name"

Installation
------------

The package is available on PyPI and is passing tests on Python 2.7, 3.3 and 3.4
Working on getting this on PyPI

.. code-block:: bash

    pip install flask_datatables

Usage
-----


This is SUPER simple. In datatables I provide a function called get_resource that can be used to create a
datatables api endpoint with full flask-restless style filtering built in.


Additional data such as hyperlinks can be added via DataTable.add_data, which accepts a callable that is called for
each instance. Check out the usage example below for more info.


Example
-------

**models.py**

.. code-block:: python

    class User(Base):
        __tablename__ = 'users'

        id = Column(Integer, primary_key=True)
        full_name = Column(Text)
        created_at = Column(DateTime, default=datetime.datetime.utcnow)



    class Address(Base):
        __tablename__ = 'addresses'

        id = Column(Integer, primary_key=True)
        description = Column(Text)
        user_id = Column(Integer, ForeignKey('users.id'))

        user = relationship("User", backref=backref("address", uselist=False))

        def __repr__(self):
            return "{}".format(self.description)


**api.py**

.. code-block:: python

    from model import Session, User, Address
    from datatables import *

    app = Flask(__name__)
    api = Api(app)
    # add User resource
    resource, path, endpoint = get_resource(Resource, User, Session, basepath="/")
    api.add_resource(resource, path, endpoint=endpoint)

    # add Address resource
    resource, path, endpoint = get_resource(Resource, Address, Session, basepath="/")
    api.add_resource(resource, path, endpoint=endpoint)

    if __name__ == '__main__':
        app.run(host='127.0.0.1', port=5001, debug=True)



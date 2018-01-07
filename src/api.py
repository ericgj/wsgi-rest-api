import re
from itertools import chain
from functools import reduce

from webob.exc import (
    HTTPException, HTTPInternalServerError, HTTPNotFound, HTTPUnprocessableEntity
)
from jsonschema import validate, ValidationError, RefResolver


class Api:
    def __init__(self, resources, id, name=u'', schema=None,
                 schemas=[], config={}):
        self.config = config
        root = (
            Resource(name=name, id=id, schema=schema, resources=resources, read=self.read)
        )
        self._index = index_matchers( compile_resource(root, [], schemas) )
        # print(self._index)
        self._start = compile_start( [ name, id ] )

        #  TODO: build a reverse index to implement `url_for`

    def match(self, method, path):
        path_len = len( path.strip(u'/').split(u'/') )
        candidates = self._index.get((path_len, method), [])
        if len(candidates) == 0:
            raise HTTPNotFound()
        else:
            try:
                return next( match_path(path, candidates) )
            except StopIteration:
                raise HTTPNotFound()

    def matches_start(self, path):
        return ( not self._start.match( path ) is None )

    def read( self, request, params, config ):
        pass  # TODO


class Resource:
    def __init__(self, name, id=None, schema=None, 
                 list=None, read=None, create=None, update=None, delete=None, 
                 resources=[]):
        self.name = name
        self.id = id
        self.schema = schema
        self.list = list
        self.read = read
        self.create = create
        self.update = update
        self.delete = delete
        self.resources = resources


class Matcher:
    def __init__(self, length, method, template, req_schema, res_schema, func):
        self.length = length
        self.method = method
        self.template = template
        self.req_schema = req_schema
        self.res_schema = res_schema
        self.func = func

    def __repr__(self):
        return (
            "Matcher(%d, %s, %s, %s, %s, <func>)" % 
                ( self.length, 
                  self.method.__repr__(),
                  self.req_schema.__repr__(),
                  self.res_schema.__repr__(),
                  self.template.__repr__()
                )
        )


class Handler:
    def __init__(self, req_schema, res_schema, params, func):
        self.req_schema = req_schema
        self.res_schema = res_schema
        self.params = params
        self.func = func

    def __call__(self, req, config={}):
        if not self.req_schema is None:
            try:
                validate( req.json_body, self.req_schema )
            except ValidationError as e:
                raise HTTPUnprocessableEntity( detail=str(e) )

        res = self.func( req, self.params, config=config )

        if not self.res_schema is None:
            try:
                validate( res.json_body, self.res_schema )
            except ValidationError as e:
                raise HTTPUnprocessableEntity( 
                    detail=str(e),
                    comment="\n".join( 
                        str(e_) for e_ in sorted( e.context, key=lambda x: x.schema_path )
                    )
                )

        return res


    def __repr__(self):
        return (
            "Handler(%s, %s, %s, <func>)" % 
                ( self.req_schema.__repr__(), 
                  self.res_schema.__repr__(), 
                  self.params.__repr__()
                )
        )




# Routing implementation



def compile_resource( resource, prefix, schemas={} ):
    id = capture_id( resource.id )
    ancestor_id = capture_ancestor_id(resource.name, resource.id)
    name = re.escape(resource.name)
    (collection, entity) = compile( prefix, name, id )
    collection_len = len(prefix) + 1
    entity_len = len(prefix) + 2
    
    # TODO: get correct schema from schemas for each of list/create/read/update/delete

    return (
        ([ Matcher( 
               length=collection_len, 
               method=u'GET', 
               template=collection, 
               req_schema=None, 
               res_schema=None, 
               func=resource.list 
           ) 
         ] if resource.list else [] )  +
        ([ Matcher( 
               length=collection_len, 
               method=u'POST', 
               template=collection, 
               req_schema=None, 
               res_schema=None, 
               func=resource.create 
           ) 
         ] if resource.create else [] )  +
        ([ Matcher( 
               length=entity_len,
               method=u'GET', 
               template=entity, 
               req_schema=None, 
               res_schema=None, 
               func=resource.read 
           ) 
         ] if resource.read else [] ) +
        ([ Matcher( 
               length=entity_len, 
               method=u'POST', 
               template=entity, 
               req_schema=None, 
               res_schema=None, 
               func=resource.update 
           ) 
         ] if resource.update else [] ) +
        ([ Matcher( 
               length=entity_len, 
               method=u'DELETE', 
               template=entity, 
               req_schema=None, 
               res_schema=None, 
               func=resource.delete 
           ) 
         ] if resource.delete else [] ) +    
        list( 
            chain.from_iterable(
                [ compile_resource(sub, prefix + [name, ancestor_id])
                    for sub in resource.resources
                ]
            )
        )
    )


def index_matchers( matchers ):
    def _index( acc, matcher ):
        grp = acc.get((matcher.length, matcher.method), [])
        grp.append(matcher)
        acc[(matcher.length, matcher.method)] = grp
        return acc
    return reduce(_index, matchers, {})


def match_path( path, matchers ):
    for matcher in matchers:
        m = matcher.template.match(path)
        if m is None:
            continue
        else:
            yield Handler( 
                    req_schema=matcher.req_schema, 
                    res_schema=matcher.res_schema, 
                    func=matcher.func, 
                    params=m.groupdict()  
            )


def capture_id( id ):
    return u'(?P<id>' + id + u')'

def capture_ancestor_id( name, id ):
    return u'(?P<' + py_identifier(name) + u'_id>' + id + u')'

def py_identifier(s):
    return re.sub('\W|^(?=\d)', '_', s)

def compile( prefix, name, id ):
    return [
        re.compile(
            u"\\/" + 
            u"\\/".join(prefix + [name]) + 
            u"(?:\\/){0,1}\Z" 
        ),
        re.compile(
            u"\\/" + 
            u"\\/".join(prefix + [name, id]) + 
            u"(?:\\/){0,1}\Z" 
        )
    ]

def compile_start( prefix ):
    return re.compile(u"\\/" + u"\\/".join(prefix))


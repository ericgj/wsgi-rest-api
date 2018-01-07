import sys
import traceback as tb

import webob
from webob.response import Response
from webob.exc import *
from api import Api, Resource


def wsgi( app ):
    def _wsgi( environ, start_response ):
        req = webob.Request(environ)
        res = app(req)
        return res(environ, start_response)
    return _wsgi

def dispatch_multiple( apis ):
    def _dispatch( request ):
        iter = ( api for api in apis if api.matches_start(request.path) )

        for api in iter:
            try:
                handler = api.match( request.method, request.path )
                return handler( request, api.config )
            
            except HTTPNotFound:
                continue

            except HTTPException as e:
                return e

            except Exception as e:
                return (
                    HTTPInternalServerError( 
                        detail=str(e), 
                        comment="\n".join( tb.format_list( tb.extract_tb( sys.exc_info()[2] ) ) )
                    )
                )

        return HTTPNotFound()

    return _dispatch


def dispatch( api ):
    def _dispatch( request ):
        try:
           handler = api.match( request.method, request.path )
           return handler( request, api.config )
        
        except HTTPException as e:
           return e

        except Exception as e:
           return (
               HTTPInternalServerError( 
                   detail=str(e), 
                   comment="\n".join( tb.format_list( tb.extract_tb( sys.exc_info()[2] ) ) )
               )
          )
    return _dispatch




if __name__ == "__main__":

  from webtest import TestApp

  def r1_list(request, params, config):
      return webob.Response( json_body= [1,2,3] )

  def r1_1_1_read(request, params, config):
      return webob.Response( json_body=params )

  api = (
      Api([
          Resource( name="r1", id=r"\d+", list=r1_list,
             resources=[
                 Resource( name="r1-1", id=r"\d+", 
                     resources=[ 
                         Resource( name="r1-1-1", id=r"\w+", read=r1_1_1_read )
                     ]
                )
            ]
         )],     
          name="api", id="1"
      )
  )

  print( api.matches_start(u'/api/1/b/c/d') )

  app = TestApp( wsgi( dispatch(api) ) )

  resp = app.get(u'/api/1/r1')
  print(resp.json)

  resp = app.get(u'/api/1/r1/2/r1-1/3/r1-1-1/4/')
  print(resp.json)



         

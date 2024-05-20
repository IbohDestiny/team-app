from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from teams_app.models import Relationship, Team, Role, Status
from .api_serializer import UsersTeamsSerializer, AdditionalTeam, TeamSerializer, RelationshipSerializer
from rest_framework.exceptions import NotFound, AuthenticationFailed, PermissionDenied
from django.db.models.functions import Lower
from rest_framework import permissions 
from django.contrib.auth.models import User
from django.http.response import HttpResponseRedirect, JsonResponse
from django.http.request import HttpRequest
from .serializers.teams_list import AllTeamSerializer
from django.shortcuts import get_object_or_404
import hashlib

def teams_permission_check(request:HttpRequest, username):
    token = request.META.get("HTTP_TEAMS_TOKEN")
    if not token:
        raise AuthenticationFailed("No Token Found")
    expected_token = hashlib.sha256((username + "AbsencePlanner").encode()).hexdigest()
    if expected_token != token:
        raise PermissionDenied("Invalid Token")

class UserTeamViewSet(viewsets.ModelViewSet):

    serializer_class = UsersTeamsSerializer

    def get_queryset(self):
        username = self.request.query_params.get("username")
        if not username:
            raise NotFound(detail="Error, no given username", code=404)
        elif not User.objects.filter(username=username).exists():
            raise NotFound(detail="Error, invalid username", code=404)
        return Relationship.objects.filter(user__username=username, status_id=1).all()

class MembersTeamViewSet(viewsets.ModelViewSet):

    serializer_class = AdditionalTeam

    def get_queryset(self):
        team = self.request.query_params.get("team")
        id = self.request.query_params.get("id")
        
        if not team and not id:
            raise NotFound(detail="Error, no given team", code=404)
        
        if self.request.query_params.get("team"):
            if not Team.objects.get(name=team):
                raise NotFound(detail="Error, invalid team", code=404)
            return Team.objects.filter(name=team).all()
        elif self.request.query_params.get("id"):
            if not Team.objects.get(id=id):
                raise NotFound(detail="Error, invalid team", code=404)
            return Team.objects.filter(id=id).all()

        

class AllUserTeamsViewSet(viewsets.ModelViewSet):

    serializer_class = AllTeamSerializer

    def get_queryset(self):
        username = self.request.query_params.get("username")
        if not username:
            raise NotFound(detail={"error_msg": "Error, no given username", "code": "N"}, code=404)
        elif not User.objects.filter(username=username).exists():
            raise NotFound(detail={"error_msg": "Error, invalid username", "code": "I"}, code=404)

        teams_permission_check(self.request, username)

        return Relationship.objects.order_by(Lower("role__id")).filter(user__username=username, status_id=1).all()

class TeamView(viewsets.ModelViewSet):

    serializer_class = TeamSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        username = self.request.query_params.get("username")
        if not username:
            raise NotFound(detail="Error, no given username", code=404)
        elif not User.objects.filter(username=username).exists():
            raise NotFound(detail="Error, invalid username", code=404)
        
        exclude_list = Relationship.objects.filter(user__username=username, status_id=1).values_list('team_id')

        return Team.objects.filter(private=False).exclude(id__in=exclude_list)
    
    def create(self, request:HttpRequest):
        #Create Team
        team_data = request.data.dict()
        if team_data.get("private") is not None:
            if team_data["private"] == "on":
                team_data["private"] = True
            else:
                team_data["private"] = False
        else:
            team_data["private"] = False
        
        serializer = TeamSerializer(data=team_data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        #Add Team Owner
        #Check if username exists
        if not User.objects.filter(username=request.data["username"]).exists():
            raise NotFound(detail="Error, invalid username", code=404)
        
        owner_data = {
            "user": User.objects.get(username=request.data["username"]),
            "team": Team.objects.get(name=serializer.data["name"]),
            "role": Role.objects.get(role="Owner"),
            "status": Status.objects.get(status="Active")
        }
        
        owner_serializer = RelationshipSerializer(data = owner_data)
        owner_serializer.is_valid()
        owner_serializer.save()

        team_id = Team.objects.get(name=serializer.data["name"]).id
        return JsonResponse(data={"message": "success", "id": team_id}, status=200)

class TeamManager(viewsets.ModelViewSet):

    serializer_class = RelationshipSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Relationship.objects.all()
    
    def get_object(self):
        rel = get_object_or_404(Relationship, user_id=self.request.data["user"])
        return rel
    
    def create(self, request:HttpRequest):
        serializer = RelationshipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return HttpResponseRedirect(redirect_to="http://" + request.data["url"] + "/teams/")
    
    def destroy(self, request:HttpRequest, pk=None):
        rel = Relationship.objects.get(team=request.data["team"], user__username=request.data["user"])
        if rel is not None:
            rel.delete()
        else:
            return JsonResponse(data={"message": "Failed to find relationship."}, status=404)
        
        return JsonResponse(status=200)
'use strict';

/**
 * @ngdoc function
 * @name ngappApp.controller:CrashController
 * @description
 * # TopbucketsCtrl
 * Controller of the ngappApp
 */
angular.module('PartyCrasherApp')
.controller('CrashController', function (
  $scope,
  $routeParams,
  PartyCrasher,
  CrashReport
) {
  var project = $routeParams.project,
    id = $routeParams.id;
    
  PartyCrasher.fetchReport({ project, id })
    .then(rawReport => {
      var report = $scope.crash = new CrashReport(rawReport);
      $scope.stack = report.stackTrace;
      $scope.context = report.contextData;
      var buckets = report.buckets;
      buckets = _.toPairs(buckets);
      buckets.sort((a, b) => {
          return a[0] - b[0];
      });
      $scope.buckets = buckets;
      $scope.date = report.date;
      
      var precedentId = rawReport['buckets']['top_match']['report_id'];
      var precedentProject = rawReport['buckets']['top_match']['project'];
      $scope.precedentScore = rawReport['buckets']['top_match']['score'];
      
      PartyCrasher.fetchReport({project: precedentProject, id: precedentId})
        .then(rawPrecedent => {
          var precedent = new CrashReport(rawPrecedent);
          $scope.precedent = precedent;
        });
    });
});

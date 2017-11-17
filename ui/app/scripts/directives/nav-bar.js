angular.module('PartyCrasherApp')
.directive('pcNavBar', function ($log, 
                                 DEFAULT_THRESHOLD, 
                                 THRESHOLDS,
                                 COG_IMAGE,
                                 TYPE_NAMES,
                                 PROJECT_NAMES
                                ) {
  function link(scope, element, _attrs) {
    scope.COG_IMAGE=COG_IMAGE
    scope.projects = PROJECT_NAMES;
    scope.report_types = TYPE_NAMES;
    scope.groupings = [
      { value: "reports", name: "report (no grouping)" },
      { value: "buckets", name: "automatic bucket" },
    ];
  }
  
  return {
    templateUrl: 'views/nav-bar.html',
    link: link,
    scope: false
  };
});